from pydantic import BaseModel
from typing import ClassVar

import logfire
import os
from .env import Env
from .log import Log

_env = Env()
_log = Log("", "")

class Telemetry(BaseModel):
    logger: str = "logfire"
    code_source_root_path: str = "" #"/root/path"
    

    def __init__(self, **data):
        super().__init__(**data)

        if self.logger == "logfire":
            code_source = None
            logfire_token = os.getenv("LOGFIRE_TOKEN")

            
            repository=os.getenv("LOGFIRE_CODE_SOURCE")
            if repository is None:
                _log.message = "FLOWBYTE | Telemetry: You can add your code source in .env using LOGFIRE_CODE_SOURCE"
                _log.status = "warning"
                _log.print_message()
            
            else:
                code_source = logfire.CodeSource(
                    repository=repository,  
                    revision='<hash of commit used on release>',  
                    root_path=self.code_source_root_path,  
                )


                
            

            logfire.configure(token=logfire_token, environment="flowbyte", service_name="mssql", code_source=code_source)



