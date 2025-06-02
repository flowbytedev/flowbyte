# streamlit_telemetry_collector/telemetry_collector.py
import streamlit as st
import duckdb
from datetime import datetime
import os
  


class TelemetryCollector:
    """
    A class to collect and log user telemetry data in a Streamlit application.
    This class collects user information such as username, email, name, timestamp,
    You should add the below to your Streamlit secrets:
        [flowbyte.telemetry]
        path = "/path/database.duckdb"
    """
    def __init__(self):
        # Fetch the DuckDB database path from Streamlit's secrets
        try:
            self.db_path = st.secrets["flowbyte"]["telemetry"]["path"]
            # create directory in case it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        except KeyError:
            self.db_path = None
            
        if not self.db_path:
            raise ValueError("DuckDB path not found in Streamlit secrets.")
        
        
        user = st.user
        
        # Fetch user data from Streamlit's `st.user` (if available) and `st.context`
        self.username = user.get("preferred_username", "Unknown")
        self.email = user.get("email", "unknown@example.com")
        self.name = user.get("name", "Unknown User")
        self.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.page_url = st.context.url
        self.page_name = st.context.url.split("/")[-1] if st.context.url else "Unknown Page"
        self.ip_address = st.context.ip_address if st.context.ip_address else "Unknown IP"

    def collect_data(self):
        # Collects the necessary user data
        user_data = {
            "username": self.username,
            "email": self.email,
            "name": self.name,
            "timestamp": self.timestamp,
            "url": self.page_url,
            "page": self.page_name,
            "ip_address": self.ip_address
        }
        return user_data

    def log_data(self):
        # Connect to the DuckDB database and insert user data

        if not self.db_path:
            raise ValueError("DuckDB path not found in Streamlit secrets.")
        
        user_data = self.collect_data()
        
        # Connect to DuckDB
        connection = duckdb.connect(self.db_path, read_only=False)

        # Insert user data into the telemetry table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_telemetry (
                username STRING,
                email STRING,
                timestamp TIMESTAMP,
                url STRING,
                page STRING,
                name STRING,
                ip_address STRING
            );
        """)

        # Insert data into the table
        connection.execute("""
            INSERT INTO user_telemetry (username, email, timestamp, url, page, name, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_data["username"], user_data["email"], user_data["timestamp"], user_data["url"], user_data["page"], user_data["name"], user_data["ip_address"]))
        
        # Close the connection
        connection.close()

    @staticmethod
    def set_page_name(page_name: str):
        # Set the page name for telemetry
        st.session_state["page_name"] = page_name
