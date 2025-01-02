import pandas as pd
from .log import Log
from IPython.display import display



_log = Log("", "")


class DataFrame:
    """
    A class for working with DataFrames.
    """
    df: pd.DataFrame



    def __init__(self, df: pd.DataFrame):
        self.df = df
    

    def summarize_dataframe(self, n = 5, type: str = 'head', value_counts=None):
        """
        Summarizes a pandas DataFrame by displaying its head or tail, reporting its shape, checking for null values, and optionally showing value counts for specified columns.

        Args:
            df (pd.DataFrame): The DataFrame to be summarized.
            n (int, optional): Number of rows to display from the top or bottom of the DataFrame. Defaults to 5.
            type (str, optional): Specifies whether to display the top ('head') or bottom ('tail') rows of the DataFrame. Must be either 'head' or 'tail'. Defaults to 'head'.
            value_counts (Union[str, List[str], None], optional): Column name(s) for which to display value counts. If 'all', value counts for all columns are displayed. Defaults to None.

        Raises:
            ValueError: If 'type' is not 'head' or 'tail'.
            KeyError: If any column specified in value_counts does not exist in the DataFrame.

        Examples:
            >>> summarize_dataframe(df, n=3, type='head', value_counts='column_name')
            Displays the first 3 rows of the DataFrame, its shape, null value counts, and value counts for 'column_name'.

            >>> summarize_dataframe(df, value_counts=['col1', 'col2'])
            Displays the first 5 rows, shape, null value counts, and value counts for 'col1' and 'col2'.

            >>> summarize_dataframe(df, type='tail', value_counts='all')
            Displays the last 5 rows, shape, null value counts, and value counts for all columns.
        """

        # display either head or tail of the dataframe with its shape
        if type == 'head':
            display(self.df.head(n))
        elif type == 'tail':
            display(self.df.tail(n))
        else:
            _log.message = 'Enter eihter head or tail'
            _log.status = 'info'
            _log.print_message()

        _log.message = f'rows: {self.df.shape[0]}, columns: {self.df.shape[1]}'
        _log.status = 'info'
        _log.print_message()

        # print if there exist null values
        for column in self.df.columns:
            if self.df[column].isnull().sum() != 0:
                _log.message = f'{column} has {self.df[column].isnull().sum()} null value(s)'
                _log.status = 'info'
                _log.print_message()

        if value_counts != None:
            # transform to list if string
            value_counts = [value_counts] if isinstance(value_counts, str) else value_counts

            for column in value_counts:
                if column == 'all':
                    for columns in self.df.columns:
                        display(self.df[columns].value_counts())
                    break
                else:
                    display(self.df[column].value_counts())





    def add_all_dates(self, start_date=None, end_date=None, fill_values=None) -> pd.DataFrame:
        """
        Add all dates between the specified start_date and end_date to the DataFrame.
        If no start_date or end_date are provided, they default to the minimum and maximum 
        dates from the 'ds' column of the DataFrame. The function also handles filling missing 
        values for the newly added rows using the specified `fill_values` dictionary or with zeros.
        
        Parameters:
        - df (DataFrame): The input DataFrame containing at least a 'ds' column (date column).
        - start_date (str, optional): The start date for the range (in 'YYYY-MM-DD' format). Defaults to the minimum 'ds' value.
        - end_date (str, optional): The end date for the range (in 'YYYY-MM-DD' format). Defaults to the maximum 'ds' value.
        - fill_values (dict, optional): A dictionary where keys are column names and values are the fill values for missing data. Defaults to None (fills with 0).
        
        Returns:
        - DataFrame: A new DataFrame with all dates from start_date to end_date, with missing values filled.
        """

        if self.df.empty:
            raise ValueError("The DataFrame cannot be empty.")
        
        if not self.df.empty:
            # get dates range from minimum to maximum from the given dataframe
            if start_date is None:
                start_date = self.df['ds'].min()
            if end_date is None:
                end_date = self.df['ds'].max()
            
        
        
        # Generate date range from 2023-01-01 to 2025-12-31
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')

        # Convert the date range into a DataFrame
        df_dates = pd.DataFrame(date_range, columns=['ds'])

        self.df = pd.merge(df_dates, self.df, on='ds', how='left')
        self.df.sort_values(by='ds', ascending=True, inplace=True)

        # Handle global 'all_method' fill first
        if fill_values:
            all_method = fill_values.get('all_method')

            # Vectorized global method fill
            if all_method:
                if all_method == 'interpolate':
                    self.df = self.df.interpolate(method='linear', axis=0)
                else:
                    self.df = self.df.fillna(method=all_method)

            # Handle 'all_value' fill for specific value (not method)
            all_value = fill_values.get('all_value')
            if all_value is not None:
                self.df = self.df.fillna(value=all_value)

        # Vectorized column-specific method fill
        fill_mapping = {
            'mean': lambda x: x.mean(),
            'median': lambda x: x.median(),
            'min': lambda x: x.min(),
            'max': lambda x: x.max(),
            'mode': lambda x: x.mode()[0] if not x.mode().empty else None,
        }
        
        if fill_values != None:
            for col, method_v in fill_values.items():
                if col in ['all_method', 'all_value']:
                    continue  # Skip global settings already applied

                # Apply column-specific method, vectorized
                if method_v in fill_mapping:
                    self.df[col] = self.df[col].fillna(fill_mapping[method_v](self.df[col]))

                elif method_v in ['ffill', 'bfill', 'interpolate']:
                    # For methods like ffill, bfill, and interpolate
                    self.df[col] = self.df[col].fillna(method=method_v) if method_v != 'interpolate' else self.df[col].interpolate(method='linear', axis=0)

                else:
                    # For any other method, use the given value directly
                    self.df[col] = self.df[col].fillna(method_v)

        return self.df