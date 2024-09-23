import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

def mandatory_env(var: str):
    value = os.environ.get(var)
    if value:
        return value
    else:
        raise Exception(f"Missing env var '{var}'")

DEBUG = mandatory_env("DEBUG_APP") == "True"
VERY_OLD_RELAY = mandatory_env("VERY_OLD_RELAY") == "True"

HOST = mandatory_env("HOST")
PORT = int(mandatory_env("PORT"))

L1_POLKASCAN = mandatory_env("L1_POLKASCAN")
L1_BLOCKSCOUT = mandatory_env("L1_BLOCKSCOUT")
L1_DB_CONNECTION = mandatory_env("L1_DB_CONNECTION")
L1_SUBSTRATE_RPC_URL = mandatory_env("L1_SUBSTRATE_RPC_URL")

L2_POLKASCAN = mandatory_env("L2_POLKASCAN")
L2_BLOCKSCOUT = mandatory_env("L2_BLOCKSCOUT")
L2_DB_CONNECTION = mandatory_env("L2_DB_CONNECTION")
L2_SUBSTRATE_RPC_URL = mandatory_env("L2_SUBSTRATE_RPC_URL")