from .log import Log
from pydantic import BaseModel
import pyodbc
import sqlalchemy
from sqlalchemy import and_, Table, MetaData, text
import pyarrow as pa
import urllib.parse
import pandas as pd
import numpy as np
from .log import Log
from .telemetry import Telemetry
import sys
import logfire
import re
from sqlalchemy.dialects.mssql import NVARCHAR

_log = Log("", "")



class SQL:
    telemetry: Telemetry
    host: str
    # optional
    database: str
    username: str
    password: str
    


class MSSQL (SQL):
    driver: str
    connection_type: str
    connection = None

    def __init__(self, connection_type, host, database, username, password, driver, telemetry=Telemetry()):
        self.host = host
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.connection_type = connection_type
        self.connection = None # type: ignore
        self.telemetry = telemetry

        if self.telemetry.logger == "logfire":

            if self.connection_type == "sqlalchemy":
                logfire.instrument_sqlalchemy(engine=self.connection)
        else:
            _log.message = "Flowbyte uses logfire for telemetry. You can benefit from logfire by setting the logger to 'logfire' in the telemetry section of the configuration file."
            _log.status = "warning"
            _log.print_message()


    @logfire.instrument(msg_template='sql.check_database_exists')
    def check_database_exists(self):
        
        # cursor = self.connection.cursor()

        

        if self.connection_type == "sqlalchemy":
            query = text("SELECT db_id(:database)")  # Use a parameterized query
            # Get a connection from the engine and then execute the query
            with self.connection.connect() as conn:
                exists = conn.execute(query, {"database": self.database}).fetchone()[0] is not None
        else:
            # pyodbc 
            query = "SELECT db_id(?)"  # Use a parameterized query
            cursor = self.connection.cursor()
            cursor.execute(query, (self.database,))
            exists = cursor.fetchone()[0] is not None
        
        return exists
    
    @logfire.instrument(msg_template='sql.connect')
    def connect(self):

        """
        Connect to the database using the provided credentials
        """

        try:
            if self.connection_type == "pyodbc":
                self.connection = pyodbc.connect("DRIVER={" + self.driver + "};SERVER=" + self.host + ";DATABASE=" + self.database + ";UID=" + self.username + ";PWD=" + self.password +";CHARSET=UTF8") # type: ignore
            elif self.connection_type == "sqlalchemy":
                connect_string = urllib.parse.quote_plus(f"DRIVER={self.driver};SERVER={self.host};DATABASE={self.database};UID={self.username};PWD={self.password};CHARSET=UTF8")
                self.connection = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={connect_string}', fast_executemany=True) # type: ignore

            _log.message = f"Connected Successfully to: \n- Server: {self.host}\n- Database: {self.database}"
            _log.status = "success"
            _log.print_message()


        except Exception as e:
            _log.message = "Error connecting to the database"
            _log.status = "fail"
            _log.print_message(other_message=str(e))

            return None

    
    @logfire.instrument(msg_template='sql.disconnect')
    def disconnect(self):
        """
        Close the connection to the database
        
        Args:

        Returns:

        """
        if self.connection:

            if self.connection_type == "pyodbc":
                self.connection.close()
            elif self.connection_type == "sqlalchemy":
                self.connection.dispose()
            
            _log.message = "Connection closed"
            _log.status = "success"
            _log.print_message()

        else:
            _log.message = "No connection to close"
            _log.status = "fail"
            _log.print_message()

    @logfire.instrument(msg_template='sql.create_database')
    def create_database(self, database_name):
        """
        Create a new database
        """

        if self.connection_type == "sqlalchemy":
            query = f"CREATE DATABASE [{database_name}]"
            with self.connection.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(text(query))
        else:
            self.connection.autocommit = True  # ✅ REQUIRED for CREATE DATABASE
            query = f"CREATE DATABASE [{database_name}]"
            cursor = self.connection.cursor()  # type: ignore
            cursor.execute(query)  # Parameterized query to prevent SQL injection
            self.connection.autocommit = False  # Optional: restore default if needed



    @logfire.instrument(msg_template='sql.schema_exists')
    def schema_exists(self, schema_name):
        """
        Check if a schema exists in the database

        Args:
            schema_name: str - The name of the schema to check
        """

        if self.connection_type == "sqlalchemy":
            
            result = self.connection.execute(
            text("SELECT schema_id FROM sys.schemas WHERE name = :name"),
                {"name": schema_name}
            )
            return result.fetchone() is not None
        else:  # pyodbc
            cursor = self.connection.cursor()
            cursor.execute("SELECT schema_id FROM sys.schemas WHERE name = ?", (schema_name,))
            return cursor.fetchone() is not None
            

    @logfire.instrument(msg_template='sql.create_schema')
    def create_schema(self, schema_name):

        # Validate schema name to allow only alphanumeric characters, underscores, and optional square brackets
        # Regex: allows [schema_name] or schema_name formats, where schema_name contains only alphanumeric characters and underscores
        if not re.match(r'^\[?[A-Za-z0-9_]+\]?$|^[A-Za-z0-9_]+$', schema_name):
            raise ValueError(f"Invalid schema name: {schema_name}. Only alphanumeric, underscores, and optional square brackets are allowed.")
    
        # If the schema name has brackets, strip them off
        schema_name = schema_name.strip("[]")

        if self.connection_type == "sqlalchemy":

            with self.connection.connect() as connection:
                if not sqlalchemy.inspect(connection).has_schema(schema_name):
                    connection.execute(sqlalchemy.schema.CreateSchema(schema_name))
                    connection.commit()
                    print(f"Schema '{schema_name}' created successfully.")
                else:
                    print(f"Schema '{schema_name}' already exists.") 
        else:
            cursor = self.connection.cursor()
            # Check if schema exists in sys.schemas
            cursor.execute(
                "SELECT 1 FROM sys.schemas WHERE name = ?",
                (schema_name,)
            )
            result = cursor.fetchone()

            # If schema does not exist, create it
            if result is None:
                cursor.execute(f"CREATE SCHEMA {schema_name}")
                self.connection.commit()
                print(f"Schema '{schema_name}' created successfully.")
            else:
                print(f"Schema '{schema_name}' already exists.") 


    @logfire.instrument(msg_template='sql.table_exists')
    def table_exists(self, schema_name, table_name):
        """
        Check if a table exists in the database

        Args:
            schema_name: str - The name of the schema to check
            table_name: str - The name of the table to check
        """
        query = """
            SELECT 1
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table
        """

        if self.connection_type == "sqlalchemy":
            with self.connection.connect() as conn:
                result = conn.execute(
                    text(query),
                    {"schema": schema_name, "table": table_name}
                )
                return result.fetchone() is not None
        else: #pyodbc
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
                (schema_name, table_name)
            )
            return cursor.fetchone() is not None

    
    @logfire.instrument(msg_template='sql.get_data.convert_pyarrow_columns')
    def convert_pyarrow_columns(self, chunk_df, category_columns=None, bool_columns=None, float_columns=None, integer_columns = None, object_columns=None, timestamp_columns=None):
        """
        Convert columns in a DataFrame to the specified data types using PyArrow

        Args:
            df: DataFrame - The DataFrame to convert
            category_columns: list - List of column names to be converted to category dtype
            bool_columns: list - List of column names to be converted to bool dtype
            float_columns: list - List of column names to be converted to float dtype

        Returns:
            df: DataFrame - The DataFrame with the columns converted
        """

        desired_precision = 38
        desired_scale = 20

        # Convert columns based on specified data types
        for columns, dtype in [(category_columns, 'category'), 
                                (bool_columns, 'bool'), 
                                (float_columns, 'float64'),
                                (integer_columns, 'int64'),
                                (object_columns, 'object'),
                                (timestamp_columns, 'timestamp')

                                ]:
            if columns:  
                for column in columns:
                    if column in chunk_df.column_names:
                        if dtype == "category":
                            # Convert column to string first, then cast to dictionary
                            chunk_df = chunk_df.set_column(
                                chunk_df.schema.get_field_index(column),
                                column,
                                chunk_df.column(column).cast(pa.string()).dictionary_encode()
                            )
                        elif dtype == "timestamp":
                            # Convert to timestamp[us] (or another timestamp type like timestamp[s])
                            chunk_df = chunk_df.set_column(
                                chunk_df.schema.get_field_index(column),
                                column,
                                chunk_df.column(column).cast(pa.timestamp('us'))
                            )

                        elif dtype == "object":
                            # Convert to string (object type is typically a string in pandas)
                            chunk_df = chunk_df.set_column(
                                chunk_df.schema.get_field_index(column),
                                column,
                                chunk_df.column(column).cast(pa.string())
                            )
                        else:
                            chunk_df = chunk_df.set_column(
                                chunk_df.schema.get_field_index(column),
                                column,
                                chunk_df.column(column).cast(pa.type_for_alias(dtype))  
                            )

        # Cast decimal columns to desired precision and scale
        for column in chunk_df.column_names:
            column_type = chunk_df.schema.field(column).type
            if pa.types.is_decimal(column_type):
                # Cast to the desired decimal type with precision 38 and scale 20
                chunk_df = chunk_df.set_column(
                    chunk_df.schema.get_field_index(column),
                    column,
                    chunk_df.column(column).cast(pa.decimal128(desired_precision, desired_scale))
                )


        return chunk_df


    @logfire.instrument(msg_template='sql.get_data')
    def get_data(self, query, chunksize=10000, category_columns=None, bool_columns=None, 
                 float_columns=None, integer_columns=None, 
                 object_columns=None, timestamp_columns=None, 
                 progress_callback=None, *args, **kwargs) -> pd.DataFrame: # type: ignore
        """
        Get data from the database in chunks, converting specified columns to the appropriate data types.

        Args:
            query: str - SQL query to be executed
            chunksize: int - Number of rows per chunk
            category_columns: list - List of column names to be converted to category dtype
            bool_columns: list - List of column names to be converted to bool dtype
            float_columns: list - List of column names to be converted to float dtype
            integer_columns: list - List of column names to be converted to int dtype
            object_columns: list - List of column names to be converted to object (string) dtype
            timestamp_columns: list - List of column names to be converted to timestamp dtype
            progress_callback: function - Function to call to report progress. For example:
                def print_progress(records):
                    print(records)

                # Usage:
                sql.get_data(query, progress_callback=print_progress)
            *args, **kwargs - Additional arguments to pass to the progress_callback function

        Returns:
            df: DataFrame - The concatenated DataFrame containing the data, or None if an error occurred.

        Description:
            This function executes the provided SQL query and retrieves the data in chunks. It then converts
            specified columns to the appropriate data types (e.g., category, bool, float, integer, and decimal) 
            based on the input parameters. The function also handles any necessary rounding for the specified 
            columns and aligns all chunks to ensure that the column structure is consistent across all chunks.

            The function also includes a progress callback that can be used to track the status of the data retrieval 
            process. After fetching all the chunks, the function concatenates them into a single DataFrame and returns it.

            In case of any errors (e.g., casting errors or SQL execution issues), the function returns `None` and logs 
            an error message.

        Note:
        - It is important to define the column names for each type (category, bool, float, int, decimal, object, timestamp).
        - If a column is not defined in the corresponding list, it may not be cast to the correct type, which could result in errors during processing.
        - If columns contain NULL values or different types across chunks, it could lead to schema errors. 
        - Ensure columns with NULL values are defined properly in their respective types to avoid errors.
        """

        chunks = []
        total_records = 0
        column_names = set()




        try:
            if self.connection_type == "sqlalchemy":
                cursor = self.connection.connect() # type: ignore
                query = text(query)
                
                result = cursor.execute(query)

                column_names = result.keys()

            else:
                cursor = self.connection.cursor()  # type: ignore
                

                result = cursor.execute(query)
                column_names = [column[0] for column in cursor.description]
                
            
            

            total_records = 0

            while True:

                if self.connection_type == "sqlalchemy":
                    rows = result.fetchmany(chunksize)
                else:
                    rows = cursor.fetchmany(chunksize)
                if not rows:
                    break

                # Create a pyarrow Table from the fetched rows

                
                # chunk_df = pa.Table.from_pydict(dict(zip([column[0] for column in cursor.description], zip(*rows))))
                chunk_df = pa.Table.from_pydict(dict(zip(column_names, zip(*rows))))


                # Convert columns based on specified data types
                chunk_df = self.convert_pyarrow_columns(chunk_df=chunk_df, 
                                                        category_columns=category_columns, 
                                                        bool_columns=bool_columns, 
                                                        float_columns=float_columns,
                                                        integer_columns=integer_columns,
                                                        object_columns=object_columns,
                                                        timestamp_columns=timestamp_columns)


                chunks.append(chunk_df)
            

                # Print the progress if progress_callback is provided
                if progress_callback:
                    total_records += chunk_df.num_rows
                    memory_used = sum(chunk.nbytes for chunk in chunks) / 1024 ** 2
                    message = f"Records {total_records}  | Memory Used: {memory_used} MB"
                    
                    # Move the cursor up one line and clear the line
                    sys.stdout.flush()
                    sys.stdout.write('\033[F')  # Cursor up one line
                    sys.stdout.write('\033[K')  # Clear to the end of the line

                    progress_callback(message, *args, **kwargs)

            # Close the SQL connection
            self.disconnect()

            # Concatenate all chunks into a single Table
            if chunks:
                df = pa.concat_tables(chunks).to_pandas()
            else:
                _log.message = "Query returned no data"
                _log.status = "fail"
                _log.print_message()
                df = pd.DataFrame()

            return df 

        except Exception as e:
            # Print the error message
            _log.message = "Error executing the query"
            _log.status = "fail"
            _log.print_message(other_message=str(e))

            # Print additional note about column types
            _log.message = "Note: It is important to define the expected column types explicitly (category, bool, float, int, decimal, object, timestamp)."
            _log.status = "warning"
            _log.print_message()
            

            _log.message = "If columns contain NULL values or different types across chunks, it could lead to schema errors. Ensure columns with NULL values are defined properly in their respective types to avoid errors."
            _log.status = "warning"
            _log.print_message()
            return None
        

    @logfire.instrument(msg_template='sql.get_full_data')
    def get_full_data(self, query, category_columns=None, bool_columns=None, 
                 float_columns=None, integer_columns=None,  
                 object_columns=None, timestamp_columns=None, progress_callback=None, *args, **kwargs):
        """
        Executes an SQL query and retrieves data from the database, returning it as a pandas DataFrame.

        Args:
            query : str - The SQL query to execute.
            category_columns : list, optional - List of columns to be converted to categorical (dictionary-encoded) format.
            bool_columns : list, optional - List of columns to be converted to boolean type.
            float_columns : list, optional - List of columns to be converted to float64 type.
            integer_columns : list, optional - List of columns to be converted to int64 type.
            object_columns : list, optional - List of columns to be converted to string (object) type.
            timestamp_columns : list, optional - List of columns to be converted to timestamp[us] format.
            progress_callback : function, optional - A function that receives progress updates in the form of a status message. For example:
                def print_progress(records):
                    print(records)

                # Usage:
                sql.get_full_data(query, progress_callback=print_progress)

        Returns:
            pandas.DataFrame or None
                A DataFrame containing the query results, with specified data types applied.
                Returns None if an error occurs during execution.

        Description:
            This function fetches data using a database cursor, converts it into a PyArrow Table, and applies
            type conversions based on user-specified column categories. It also supports progress reporting 
            via a callback function.

        """
        

        desired_precision = 38
        desired_scale = 20




        try:
            if self.connection_type == "sqlalchemy":
                with self.connection.connect() as conn:
                    result = conn.execute(text(query))  # No parameters here
                    rows = result.fetchall()
                    columns = list(result.keys())
            else: # pyodbc
                cursor = self.connection.cursor()  # type: ignore
                cursor.execute(query)

                # Fetch rows and column names
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]


            if not rows:
                return pd.DataFrame()

            # Convert to pyarrow Table
            df_pa = pa.Table.from_arrays([pa.array(col) for col in zip(*rows)], names=columns)

            # # Collect column names
            # column_names = set()
            # column_names.update(df_pa.column_names)

            # Convert columns based on specified data types
            for columns, dtype in [(category_columns, 'category'), 
                                    (bool_columns, 'bool'), 
                                    (float_columns, 'float64'),
                                    (integer_columns, 'int64'),
                                    (object_columns, 'object'),
                                    (timestamp_columns, 'timestamp')
                                    ]:
                if columns:  
                    for column in columns:
                        if column in df_pa.column_names:
                            if dtype == "category":
                                # Convert column to string first, then cast to dictionary
                                df_pa = df_pa.set_column(
                                    df_pa.schema.get_field_index(column),
                                    column,
                                    df_pa.column(column).cast(pa.string()).dictionary_encode()
                                )
                            elif dtype == "timestamp":
                                # Convert to timestamp[us] (or another timestamp type like timestamp[s])
                                df_pa = df_pa.set_column(
                                    df_pa.schema.get_field_index(column),
                                    column,
                                    df_pa.column(column).cast(pa.timestamp('us'))
                                )

                            elif dtype == "object":
                                # Convert to string (object type is typically a string in pandas)
                                df_pa = df_pa.set_column(
                                    df_pa.schema.get_field_index(column),
                                    column,
                                    df_pa.column(column).cast(pa.string())
                                )
                            else:
                                df_pa = df_pa.set_column(
                                    df_pa.schema.get_field_index(column),
                                    column,
                                    df_pa.column(column).cast(pa.type_for_alias(dtype))  
                                )

            # Progress reporting
            if progress_callback:
                total_records = df_pa.num_rows
                memory_used = df_pa.nbytes / 1024**2  # Convert bytes to MB
                message = f"Records: {total_records} | Memory Used: {memory_used:.2f} MB"

                sys.stdout.flush()
                sys.stdout.write('\033[F\033[K')  # Move up and clear line
                progress_callback(message, *args, **kwargs)

            # Convert to pandas DataFrame
            df = df_pa.to_pandas()

            return df

        except Exception as e:
            # Print the error message
            _log.message = "Error executing the query"
            _log.status = "fail"
            _log.print_message(other_message=str(e))
            return None


    @logfire.instrument(msg_template='sql.insert_data')
    def insert_data(self, schema: str, table_name: str, insert_records: pd.DataFrame, chunksize=10000, if_table_exists="append", progress_callback=None, *args, **kwargs):
        """
        Insert records into a database table
 
        Args:
            schema: str - The schema name of the table
            table_name: str - The name of the table to insert records into
            insert_records: DataFrame - The records to insert, where each row is a record
            chunksize: int - The number of rows to insert in each chunk
            if_table_exists: str - The action to take if the table already exists. Options are 'fail', 'replace', 'append', 'truncate', 'drop'
            progress_callback: function - Optional. A callback function to show progress. For example:
                def print_progress(records):
                    print(records)
 
                # Usage:
                sql.insert_data(schema=schema, table_name=table_name, insert_records=df, progress_callback=print_progress)
 
        Returns:
            None
        """
       
        # connect_string = urllib.parse.quote_plus(f"DRIVER={self.driver};SERVER={self.host};DATABASE={self.database};UID={self.username};PWD={self.password};CHARSET=UTF8")
        # engine = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={connect_string}', fast_executemany=True) # type: ignore
 
        is_pyodbc = False
        if self.connection_type == 'pyodbc':
            is_pyodbc = True
            _log.message = "Only sqlalchemy connection is supported for insert_data.\n"
            _log.status = "warning"
            _log.print_message()
            self.connection_type = 'sqlalchemy'
            self.connect()
            # sys.stdout.write('Connection converted to sqlalchemy.\n')
            _log.message = "Connection converted to sqlalchemy.\n"
            _log.status = "warning"
            _log.print_message()

            
 
        total = insert_records.shape[0]
        print(f"Inserting {total} rows...")
        # with engine.connect() as conn:
 
        # Force NVARCHAR for all string/object columns
        unicode_cols = insert_records.select_dtypes(include=["object", "string"]).columns
        dtype_dict = {col: NVARCHAR(length=None) for col in unicode_cols}
 
        for i in range(0, total, chunksize):
            # print the values as details
            insert_records.iloc[i:i+chunksize].to_sql(table_name, self.connection, if_exists=if_table_exists, index=False, chunksize=chunksize, schema=schema, dtype=dtype_dict) # type: ignore
            if(i + chunksize > total):
                print(f"Inserted {total} rows out of {total} rows")
               
            else:
                print(f"Inserted {i + chunksize} rows out of {total} rows")
           
            # Print the progress if progress_callback is provided
            if progress_callback:
                chunk_df = insert_records.iloc[i:i+chunksize]
                total_records = i + len(chunk_df)
                message = f"Inserted {total_records} Records out of {total} rows"
 
                sys.stdout.flush()
                sys.stdout.write('\033[F')  # Move cursor up one line
                sys.stdout.write('\033[K')  # Clear line
 
                progress_callback(message, *args, **kwargs)
 
        if is_pyodbc==True:
            self.connection_type = 'pyodbc'
            _log.message = "Connection returned to pyodbc.\n"
            _log.status = "warning"
            _log.print_message()
            
 
 
 
 

    @logfire.instrument(msg_template='sql.update_data')
    def update_data(self, schema_name, table_name, update_records, keys):
        """
        Update records in a database table based on the provided keys.

        Args:
            engine (sqlalchemy.engine.base.Engine): The SQLAlchemy engine to use for the database connection.
            schema (str): The schema name of the table.
            table_name (str): The name of the table to update.
            update_records (list of dict): The records to update, where each record is a dictionary representing a row.
            keys (list of str): The keys to use for identifying records to update.

        Returns:
            None
        """

        connect_string = urllib.parse.quote_plus(f"DRIVER={self.driver};SERVER={self.host};DATABASE={self.database};UID={self.username};PWD={self.password};CHARSET=UTF8")
        engine = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={connect_string}', fast_executemany=True) # type: ignore

        metadata = MetaData()
        metadata.reflect(engine, schema=schema_name, only=[table_name])
        
        # Get the table object for the table you want to update
        your_table = Table(table_name, metadata, schema=schema_name, autoload_replace=True, autoload_with=engine)

        batch_size = 0

        with engine.connect() as conn:
            if not isinstance(update_records, list) or not all(isinstance(record, dict) for record in update_records):
                raise TypeError("update_records must be a list of dictionaries")
            
            updates_processed = 0

            data_count = len(update_records)
            
            if data_count < 1000:
                batch_size = data_count
            else:
                batch_size = 1000

            for i in range(0, len(update_records), batch_size):
                batch = update_records[i:i + batch_size]

                for record in batch:
                    conditions = []
                    for key in keys:
                        # Ensure key exists in record
                        if key not in record:
                            print(f"Key '{key}' not found in record:", record)
                            continue

                        conditions.append(your_table.c[key] == record[key])

                    stmt = your_table.update().where(and_(*conditions)).values(record)
                    conn.execute(stmt)
                    conn.commit()
                updates_processed += len(batch)

                if updates_processed % 1000 == 0:
                    print(f"{updates_processed} records updated")


    @logfire.instrument(msg_template='sql.upsert_data')
    def upsert_from_table(self, df, source_schema, target_schema, target_table, source_table, key_columns, delete_not_matched=False):
 
        """
        Update records in a target table from a source table based on the provided keys.
 
        Args:
            df (pd.DataFrame): The DataFrame containing the data to update.
            target_table (str): The name of the target table to update.
            source_table (str): The name of the source table to update from.
            key_columns (list of str): The columns to use as keys for updating records.
            delete_not_matched (bool): Whether to delete records in the target table that are not in the source table.
 
        Remarks:
            The name of the columns should be the same as the columns in the target and source tables.
 
        Returns:
            Number of records updated, query
 
        """
   
        # create list of columns excluding the key columns
        columns = df.columns.tolist()
 
        columns_list = ", ".join([f"[{col}]" for col in columns])
        values_list = ", ".join([f"source.[{col}]" for col in columns])
       
        insert_statement = f"INSERT ({columns_list}) VALUES ({values_list})"
 
        join_on_clause = " AND ".join([f"target.[{col}] = source.[{col}]" for col in key_columns])
       
        # set_clause = ", ".join([f"{target_table}.{col} = {source_table}.{col}" for col in columns])
       
 
        columns = [col for col in columns if col not in key_columns]
 
        set_clause = ", ".join([f"target.[{col}] = source.[{col}]" for col in columns])
        update_statement = f"UPDATE SET {set_clause}"
       
        # Construct the JOIN ON clause
        # join_on_clause = " AND ".join([f"{target_table}.{col} = {source_table}.{col}" for col in key_columns])
       
       
        records_updated = 0
       
 
        # Form the complete SQL query
        query = f"""
            MERGE [{target_schema}].[{target_table}] AS target
            USING [{source_schema}].[{source_table}] AS source
            ON {join_on_clause}
            WHEN MATCHED THEN
                {update_statement}
            WHEN NOT MATCHED THEN
                {insert_statement}
            """
 
        if delete_not_matched:
            delete_statement = f"DELETE"
            query += f"""
            WHEN NOT MATCHED BY SOURCE THEN
                {delete_statement}
            """
 
        query += ";"
 
 
        records_updated = self.execute_query(query)
       
 
        return records_updated, query


    @logfire.instrument(msg_template='sql.update_from_table')
    def update_from_table(self, df, target_table, source_table, key_columns):

        """
        Update records in a target table from a source table based on the provided keys.

        Args:
            df (pd.DataFrame): The DataFrame containing the data to update.
            target_table (str): The name of the target table to update.
            source_table (str): The name of the source table to update from.
            key_columns (list of str): The columns to use as keys for updating records.

        Remarks:
            The name of the columns should be the same as the columns in the target and source tables.

        Returns:

        """
    
        # create list of columns excluding the key columns
        columns = df.columns.tolist()
        columns = [col for col in columns if col not in key_columns]
        
        set_clause = ", ".join([f"{target_table}.{col} = {source_table}.{col}" for col in columns])
        
        
        # Construct the JOIN ON clause
        join_on_clause = " AND ".join([f"{target_table}.{col} = {source_table}.{col}" for col in key_columns])
        
        # Form the complete SQL query
        query = f"""
        UPDATE {target_table}
        SET
            {set_clause}
        FROM {target_table}
        JOIN {source_table}
        ON {join_on_clause}
        """

        self.connection.execute(query) # type: ignore

        self.connection.commit() # type: ignore


    @logfire.instrument(msg_template='sql.truncate_table')
    def truncate_table(self, schema_name, table_name):
        """
        Truncate a table in the database

        Args:
            schema_name: str - The name of the schema containing the table
            table_name: str - The name of the table to truncate
        """

        query = f"TRUNCATE TABLE {schema_name}.{table_name}"

        if self.connection_type == "sqlalchemy":

            cursor = self.connection.connect()
            cursor.execute(text(query))
            cursor.commit()
        else:
            cursor = self.connection.cursor()  # type: ignore
            cursor.execute(query)
            self.connection.commit() # type: ignore


    
    @logfire.instrument(msg_template='sql.delete_data')
    def delete_data(self, schema_name, table_name):
        """
        Delete data from a table in the database

        Args:
            schema_name: str - The name of the schema containing the table
            table_name: str - The name of the table to delete data from
        """
        if self.connection_type == "pyodbc":
            cursor = self.connection.cursor() # type: ignore
            cursor.execute(f"DELETE FROM [{schema_name}].[{table_name}]")
            self.connection.commit() # type: ignore
        elif self.connection_type == "sqlalchemy":
            with self.connection.connect() as conn:
                conn.execute(text(f"DELETE FROM [{schema_name}].[{table_name}]"))
                # Depending on your SQLAlchemy version and configuration, you might need to commit
                conn.commit()
        else:
            raise ValueError("Invalid connection type. Use 'pyodbc' or 'sqlalchemy'.")


    @logfire.instrument(msg_template='sql.delete_data_with_conditions')
    def delete_data_with_conditions(self, schema_name, table_name, conditions):
        """
        Delete data from a table in the database based on the provided conditions

        Args:
            schema_name: str - The name of the schema containing the table
            table_name: str - The name of the table to delete data from
            conditions: str - The conditions to use for deleting data
        """


        if self.connection_type == "pyodbc":
            cursor = self.connection.cursor() # type: ignore
            cursor.execute(f"DELETE FROM [{schema_name}].[{table_name}] WHERE {conditions}")
            self.connection.commit() # type: ignore
        elif self.connection_type == "sqlalchemy":
            with self.connection.connect() as conn:
                conn.execute(text(f"DELETE FROM [{schema_name}].[{table_name}] WHERE {conditions}"))
                # Depending on your SQLAlchemy version and configuration, you might need to commit
                conn.commit()
        else:
            raise ValueError("Invalid connection type. Use 'pyodbc' or 'sqlalchemy'.")





    

    # Function to execute a query based on the connection type sqlalchmey or pyodbc and returns the row count
    @logfire.instrument(msg_template='sql.execute_query')
    def execute_query(self, query):
        """
        Execute a query and return the row count

        Args:
            query: str - The query to execute

        Returns:
            row_count: int - The number of rows affected by the query
        """

        # if self.connection_type == "sqlalchemy":
        #     cursor = self.connection.connect()
        #     cursor.execute(text(query))
        #     cursor.commit()

        # else:
        #     cursor = self.connection.execute(query)
        #     self.connection.commit() # type: ignore
        #     records_updated = cursor.rowcount

        row_count = 0

        if self.connection_type == "sqlalchemy":
            with self.connection.begin() as conn:
                result = conn.execute(text(query))
                row_count = result.rowcount if result.rowcount is not None else 0
        else:
            cursor = self.connection.cursor()
            cursor.execute(query)
            row_count = cursor.rowcount
            self.connection.commit()

        return row_count

