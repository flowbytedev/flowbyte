import msal
import requests
import pandas as pd
from .log import Log


_log = Log("", "")

class PowerBI:
    client_id: str
    client_secret: str
    tenant_id: str
    scope: list
    access_token = None
    

    def __init__(self, client_id: str, client_secret: str, tenant_id: str, scope: list):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.scope = scope


    def get_authority(self):
        """
        Get the authority URL for Power BI Service
        """
        
        return f"https://login.microsoftonline.com/{self.tenant_id}"
    

    def authenticate(self):
        """
        Authenticate to Power BI Service
        """

        authority = self.get_authority()

        app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=authority
        )

        result = app.acquire_token_for_client(scopes=self.scope)
        

        if 'access_token' in result: # type: ignore
            self.access_token = result['access_token'] # type: ignore
            _log.message = "Authentication successful"
            _log.status = "success"
            _log.print_message()
        else:
            raise Exception("Authentication failed")


    def user_is_authenticated(self):
        if self.access_token:
            return True
        



class Workspace():
    workspace_id: str
        





class Dataset(Workspace):
    dataset_id: str
    powerbi: PowerBI

    # super
    def __init__(self, dataset_id: str, workspace_id: str, powerbi: PowerBI):
        self.powerbi = powerbi
        self.workspace_id = workspace_id
        self.dataset_id = dataset_id
        
        
        


    


    def get_refreshes(self, last_n: int = 1):
        """
        Get the refreshes of the dataset

        Args:
            last_n: int - Number of refreshes to get

        Returns:
            df: pd.DataFrame - DataFrame of the refreshes
        """

        if not self.powerbi.user_is_authenticated():
            raise Exception("User is not authenticated")

        url = f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/datasets/{self.dataset_id}/refreshes?$top={last_n}"

        

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.powerbi.access_token}"
        }

        response = requests.get(url, headers=headers)


        value = response.json()['value']

        df = pd.DataFrame(value)

        return df
    


    def get_last_refresh_status(self):
        """
        Get the last refresh status of the dataset

        Args:

        Returns:
            status: str - Status of the last refresh
                - Completed
                - Failed
                - Unknown -> Refreshing now
                - Disabled
        """

        if not self.powerbi.user_is_authenticated():
            log = Log("fail", "User is not authenticated")
            log.print_message()

        url = f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/datasets/{self.dataset_id}/refreshes?$top=1"

        

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.powerbi.access_token}"
        }

        response = requests.get(url, headers=headers)


        value = response.json()['value']

        # get status from value
        status = value[0]['status']

        return status
    



    def refresh(self):
        """
        Refresh the dataset

        Args:

        Returns:
            response: requests.Response - Response object
        """

        if not self.powerbi.user_is_authenticated():
            raise Exception("User is not authenticated")
        

        last_status = self.get_last_refresh_status()

        if last_status == "Unknown":
            _log.message = "Refresh already in progress"
            _log.status = "warning"
            _log.print_message()
            return


        url = f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/datasets/{self.dataset_id}/refreshes"

        

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.powerbi.access_token}"
        }


        response = requests.post(url, headers=headers)

        last_refresh = self.get_refreshes(last_n=1)



        status = self.get_last_refresh_status()

        if status == "Unknown":
            _log.message = "Refresh started"
            _log.status = "success"
            _log.print_message()
        
        else:
            _log.message = f"Error refreshing the dataset \nError Details: {last_refresh['serviceExceptionJson']}"
            _log.status = "fail"
            _log.print_message()

        return response