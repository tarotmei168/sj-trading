from dotenv import load_dotenv
import os
import shioaji as sj

load_dotenv()


def testing_stock_ordering():
    api = sj.Shioaji(simulation=True)
    accounts = api.login(
        api_key=os.environ["SJ_API_KEY"],
        secret_key=os.environ["SJ_SEC_KEY"],
    )
    print(f"Available accounts: {accounts}")

    try:
        api.activate_ca(
            ca_path=os.environ["SJ_CA_PATH"],
            ca_passwd=os.environ["SJ_CA_PASSWD"],
        )
        print("CA activated successfully")
    except Exception as e:
        print(f"CA activation skipped: {e}")

    contract = api.Contracts.Stocks["2890"]
    print(f"Contract: {contract}")

    order = sj.StockOrder(
        action=sj.constant.Action.Buy,
        price=contract.reference,
        quantity=1,
        price_type=sj.constant.StockPriceType.LMT,
        order_type=sj.constant.OrderType.ROD,
        account=api.stock_account,
    )
    print(f"Order: {order}")

    trade = api.place_order(contract=contract, order=order)
    print(f"Trade: {trade}")

    api.update_status()
    print(f"Status: {trade.status}")

    return api
