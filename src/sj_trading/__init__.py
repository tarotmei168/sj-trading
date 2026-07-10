import shioaji as sj
from dotenv import load_dotenv
import os

load_dotenv()


def show_version() -> str:
    print(f"Shioaji Version: {sj.__version__}")
    return sj.__version__


def login_test(fetch_contract=False, activate_ca=True):
    """測試登入模擬環境"""
    api = sj.Shioaji(simulation=True)
    accounts = api.login(
        api_key=os.environ["SJ_API_KEY"],
        secret_key=os.environ["SJ_SEC_KEY"],
        fetch_contract=fetch_contract,
    )
    print(f"Available accounts: {accounts}")

    if activate_ca:
        api.activate_ca(
            ca_path=os.environ["SJ_CA_PATH"],
            ca_passwd=os.environ["SJ_CA_PASSWD"],
        )
        print("login and activate ca success")
    return api
