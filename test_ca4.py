import os
from dotenv import load_dotenv
import shioaji as sj
load_dotenv()
api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ["SJ_API_KEY"], secret_key=os.environ["SJ_SEC_KEY"], fetch_contract=False)
result = api.activate_ca(ca_path=os.environ["SJ_CA_PATH"], ca_passwd='Big8825252')
print(f'CA activate: {result}')
