from pydantic import BaseModel
import os
from dotenv import load_dotenv

class Env(BaseModel):
    root_dir: str = ""

    # define the directory where the logs will be stored
    def __init__(self):
        
        root_dir = str(os.getcwd()) + "\.env"
        load_dotenv(dotenv_path=f"{root_dir}")