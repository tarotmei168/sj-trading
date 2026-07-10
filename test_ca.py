import os
from dotenv import load_dotenv
import shioaji as sj

load_dotenv()

api = sj.Shioaji(simulation=True)
accounts = api.login(
    api_key=os.environ["SJ_API_KEY"],
    secret_key=os.environ["SJ_SEC_KEY"],
    fetch_contract=True,
)
print(f"Available accounts: {accounts}")

result = api.activate_ca(
    ca_path=os.environ["SJ_CA_PATH"],
    ca_passwd=os.environ["SJ_CA_PASSWD"],
)
print(f"CA activate result: {result}")
print("All good!")
