import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from .lib.bunq_lib import BunqClient

# Load .env from project root (bunq-api folder)
env_path = Path(__file__).parent / ".env"
load_dotenv()


USER_API_KEY = os.getenv("BUNQ_API_KEY")
if not USER_API_KEY:
    print("NO USER API KEY")
    exit()
bunq_client = BunqClient(USER_API_KEY, service_name="PeterScript")


# Run these 1x to initialize your application
bunq_client.create_installation()
bunq_client.create_device_server()


bunq_client.create_session()

app = FastAPI()


@app.get("/monetary_account")
def get_monetary_account():
    response = bunq_client.request(endpoint="monetary-account", method="GET", data={})
    return response


@app.get("/request")
def request():
    endpoint = "monetary-account/"
    response = bunq_client.request(endpoint=endpoint, method="GET", data=None)
    return response


@app.get("/payment")
def payment():
    payment = bunq_client.create_payment(
        amount="0.10",
        recipient_iban="NL14RABO0169202917",
        currency="EUR",
        from_monetary_account_id="3603251",
        description="test",
    )
    return payment
