from pydantic import BaseModel
import pyodbc
import sqlalchemy
import urllib.parse
import pandas as pd
from log import *

_log = Log("", "")

class SQL:
    host: str
    database: str
    username: str
    password: str
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
            _log.print_message()

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


    def get_data(self, query, chunksize=1000, progress_callback=None, *args, **kwargs):
        """
        Get data from the database
        
        Args:
            query: str - SQL query to be executed

        Returns:
            data: list - list of tuples containing the data
        
        """

        df = pd.DataFrame()

        
        try:
            cursor = self.connection.cursor() # type: ignore
            cursor.execute(query)

            total_records = 0

            while True:
                rows = cursor.fetchmany(chunksize)
                if not rows:
                    break
                
                chunk_df = pd.DataFrame.from_records(rows, columns=[desc[0] for desc in cursor.description])
                
                total_records += len(chunk_df)

                # print the progress if progress_callback is provided
                if progress_callback:
                    progress_callback(total_records, *args, **kwargs)
                    

                df = pd.concat([df, chunk_df])

                # clear the chunk_df
                del chunk_df

            # close the sql connection
            self.disconnect()
                

            return df
        



        except Exception as e:
            # print(e)
            _log.message = "Error executing the query"
            _log.status = "fail"
            _log.print_message()
            
            return None