from pydantic import BaseModel
import pyodbc
import sqlalchemy
from sqlalchemy import and_, Table, MetaData
import urllib.parse
import pandas as pd
import numpy as np
from .log import Log
import sys

_log = Log("", "")

class SQL:
    host: str
    database: str
    username: str
    password: str


class MSSQL (SQL):
    driver: str
    connection_type: str
    connection: None

    def __init__(self, connection_type, host, database, username, password, driver):
        self.host = host
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.connection_type = connection_type
        self.connection = None


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


    def get_data(self, query, chunksize=1000, category_columns=None, bool_columns=None, float_columns=None, round_columns=None, progress_callback=None, *args, **kwargs):
        """
        Get data from the database in chunks, converting specified columns to the category dtype.

        Args:
            query: str - SQL query to be executed
            chunksize: int - Number of rows per chunk
            category_columns: list - List of column names to be converted to category dtype
            progress_callback: function - Function to call to report progress
            *args, **kwargs - Additional arguments to pass to the progress_callback function

        Returns:
            df: DataFrame - The concatenated DataFrame containing the data
        """

        chunks = []

        print(round_columns)

        try:
            cursor = self.connection.cursor()  # type: ignore
            cursor.execute(query)

            total_records = 0

            while True:
                rows = cursor.fetchmany(chunksize)
                if not rows:
                    break


                chunk_df = pd.DataFrame.from_records(rows, columns=[desc[0] for desc in cursor.description])

                if category_columns or bool_columns or round_columns or float_columns:

                    if category_columns:
                        for col in category_columns:
                            if col in chunk_df.columns:
                                chunk_df[col] = chunk_df[col].astype('category')
                    
                    if bool_columns:
                        for col in bool_columns:
                            if col in chunk_df.columns:
                                chunk_df[col] = chunk_df[col].astype('bool')

                    if float_columns:
                        for col in float_columns:
                            if col in chunk_df.columns:
                                chunk_df[col] = chunk_df[col].astype('float')

                    if round_columns:
                        print("rounding columns")
                        print()
                        chunk_df = chunk_df.round(round_columns)


                chunks.append(chunk_df)


                # Print the progress if progress_callback is provided
                if progress_callback:

                    total_records += len(chunk_df)
                    memory_used = np.sum([chunk.memory_usage().sum() for chunk in chunks]) / 1024 ** 2
                    message = f"Records {total_records}  | Memory Used: {memory_used} MB"
                    
                    # delete the last line from cmd
                    sys.stdout.flush()
    
                    # Move the cursor up one line and clear the line
                    sys.stdout.write('\033[F')  # Cursor up one line
                    sys.stdout.write('\033[K')  # Clear to the end of the line

                     
                    progress_callback(message, *args, **kwargs)


            # Close the SQL connection
            self.disconnect()

            # Concatenate all chunks into a single DataFrame
            df = pd.concat(chunks, ignore_index=True)

            return df

        except Exception as e:
            # Print the error message
            _log.message = "Error executing the query"
            _log.status = "fail"
            _log.print_message(other_message=str(e))
            return None


    def insert_data(self, schema: str, table_name: str, insert_records: pd.DataFrame, chunksize=10000):
        
        connect_string = urllib.parse.quote_plus(f"DRIVER={self.driver};SERVER={self.host};DATABASE={self.database};UID={self.username};PWD={self.password};CHARSET=UTF8")
        engine = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={connect_string}', fast_executemany=True) # type: ignore

        total = insert_records.shape[0]
        print(f"Inserting {total} rows...")
        # with engine.connect() as conn:
        for i in range(0, total, chunksize):
            # print the values as details
            insert_records.iloc[i:i+chunksize].to_sql(table_name, engine, if_exists="append", index=False, chunksize=chunksize, schema=schema) # type: ignore
            if(i + chunksize > total):
                print(f"Inserted {total} rows out of {total} rows")
            else:
                print(f"Inserted {i + chunksize} rows out of {total} rows")


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
    
        update_columns = df.columns[1:].tolist()
        
        set_clause = ", ".join([f"{target_table}.{col} = {source_table}.{col}" for col in update_columns])
        
        
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

        self.connection.execute(query)

        self.connection.commit()
