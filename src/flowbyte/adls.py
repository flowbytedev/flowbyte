import pandas as pd
from adlfs import AzureBlobFileSystem
from .log import Log


_log = Log("", "")


class ADLS:
    account_name: str
    account_key: str    
    container_name: str


    def __init__(self, account_name: str, account_key: str, container_name: str):
        self.account_name = account_name
        self.account_key = account_key
        self.container_name = container_name
        

    def generate_connection_string(self) -> str:
        """
        Generate the connection string for Azure Data Lake Storage.

        Returns:
            str: The connection string for Azure Data Lake Storage.
        """
        
        return f"DefaultEndpointsProtocol=https;AccountName={self.account_name};AccountKey={self.account_key};EndpointSuffix=core.windows.net"


    def initialize_azure_blob_file_system(self) -> AzureBlobFileSystem:
        """
        Initialize the Azure Blob File System.
        """
        return AzureBlobFileSystem(account_name=self.account_name, account_key=self.account_key)


    def list_blobs_in_directory(self, file_name, fs=None,filters=None) -> list:
        """
        Recursively list all blobs in a given directory with dynamic filtering.

        Parameters:
            fs (object): The file system object used for directory and file operations.
            file_name (str): The file suffix to filter blobs (e.g., ".csv", ".json").
            filters (dict, optional): A dictionary specifying filters for each directory level.
                                    Keys represent directory levels (e.g., "year", "month"), and values
                                    can be a string or list of allowed values to filter directories
                                    at that level (e.g., {"year": ["2024","2023"], "month": ["03", "04"]}).

        Returns:
            list: A list of file paths that match the specified filters and file suffix.
            fs: The file system object used for directory and file operations.

        Notes:
            - The function matches directory names exactly with the specified filter values
            (e.g., "03" matches "03" but not "203").
            - If no filters are provided, all files with the specified suffix are listed.
        """

        # initialize the file system if not provided
        fs = fs if fs is not None else self.initialize_azure_blob_file_system()

        def recursive_list(path, level_filters):
            
            # Base case: If no filters remain, descend into directories until files are found
            if not level_filters:
                matched_paths = []
                for sub_path in fs.ls(path):
                    if fs.isdir(sub_path):  # If it's a directory, continue exploring
                        matched_paths.extend(recursive_list(sub_path, {}))
                    elif sub_path.endswith(file_name):  # If it's a file, add it
                        matched_paths.append(sub_path)

                _log.message = f'MATCHED PATHS: {matched_paths}'
                _log.status = 'info'
                _log.print_message()

                return matched_paths
            
            # Process directories with filters
            if isinstance(level_filters, dict):  # Ensure level_filters is a dictionary
                next_filter_key, *remaining_filters = level_filters.items()
                key, allowed_values = next_filter_key
                matched_paths = []        

                for sub_path in fs.ls(path):
                    # Check if the current directory matches the filter criteria
                    if allowed_values is not None:
                        # Normalize the path and allowed values to ensure consistent matching
                        sub_path_parts = sub_path.split('/')  # Split sub_path for clarity 
                        last_part = sub_path_parts[-1]  # Get the last directory or file name
                        if not any(allowed_value == last_part for allowed_value in allowed_values):
                            continue

                    # Recurse into the next level
                    matched_paths.extend(recursive_list(sub_path, dict(remaining_filters)))

                _log.message = f'MATCHED PATHS at {key} level: {matched_paths}'
                _log.status = 'info'
                _log.print_message()

                return matched_paths    

        level_filters = filters if isinstance(filters, dict) else {}
        
        return recursive_list(self.container_name, level_filters), fs
