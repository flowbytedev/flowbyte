# streamlit_telemetry_collector/telemetry_collector.py
import streamlit as st
import duckdb
from datetime import datetime
  


class TelemetryCollector:
    """
    A class to collect and log user telemetry data in a Streamlit workspace.
    This class collects user information such as username, email, name, timestamp,
    You should add the below to your Streamlit secrets:
        [flowbyte.telemetry]
        path = "/path/database.duckdb"
    """
    workspace: str
    provider: str
    report: str
    page : str
    operation: str
    ip_address: str
    report_type: str
    consumption_method: str

    def __init__(self, provider: str = None, workspace: str = None, report: str = None, page: str = None,
                    operation: str = None, report_type: str = None, consumption_method: str = None):
        # Fetch the DuckDB database path from Streamlit's secrets
        try:
            self.db_path = st.secrets["flowbyte"]["telemetry"]["path"]
        except KeyError:
            self.db_path = None
            
        if not self.db_path:
            raise ValueError("DuckDB path not found in Streamlit secrets.")
        
        self.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.provider = provider.upper() if provider else "UNKNOWN"
        self.workspace = workspace if workspace else st.session_state.get("workspace", "default_workspace")
        self.report = report if report else "default_report"
        self.page = page if page else st.session_state.get("page_name", "unknown_page")
        self.operation = operation if operation else "ViewReport"
        self.report_type = report_type if report_type else "Streamlit"
        self.consumption_method = consumption_method if consumption_method else "Web"

        self.report_url = st.context.url
        self.ip_address = st.context.ip_address or "UNKNOWN"

        user = st.user
        self.username = user.get("preferred_username", "Unknown")
        self.email = user.get("email", "unknown@example.com")
        self.name = user.get("name", "Unknown User")
        self.view_count = 1

    def collect_data(self):
        # Collects the necessary user data
        user_data = {
            "username": self.username,
            "email": self.email,
            "timestamp": self.timestamp,
            "url": self.report_url,
            "page": self.page,
            "workspace": self.workspace,
            "provider": self.provider,
            "view_count": self.view_count,
            "report": self.report,
            "provider": self.provider,
            "operation": self.operation,
            "report_type": self.report_type,
            "consumption_method": self.consumption_method,
            "ip_address": self.ip_address
        }
        return user_data

    def log_data(self):
        # Connect to the DuckDB database and insert user data

        if not self.db_path:
            raise ValueError("DuckDB path not found in Streamlit secrets.")
        
        user_data = self.collect_data()
        
        # Connect to DuckDB
        connection = duckdb.connect(self.db_path)

        # Insert user data into the telemetry table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_telemetry (
                username VARCHAR,
                email VARCHAR,
                timestamp TIMESTAMP,
                url VARCHAR,
                page VARCHAR,
                workspace VARCHAR,
                provider VARCHAR,
                view_count INTEGER,
                report VARCHAR,
                operation VARCHAR,
                report_type VARCHAR,
                consumption_method VARCHAR,
                ip_address VARCHAR
            );
        """)

        # Insert data into the table
        connection.execute("""
            INSERT INTO user_telemetry (
                username, email, timestamp, url, page, workspace, provider, view_count, report, operation, report_type, consumption_method, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_data["username"], user_data["email"], user_data["timestamp"], user_data["url"], user_data["page"], user_data["workspace"], user_data["provider"], user_data["view_count"], user_data["report"], user_data["operation"], user_data["report_type"], user_data["consumption_method"], user_data["ip_address"])
        )

        # Close the connection
        connection.close()

    @staticmethod
    def set_page_name(page_name: str):
        # Set the page name for telemetry
        st.session_state["page_name"] = page_name
