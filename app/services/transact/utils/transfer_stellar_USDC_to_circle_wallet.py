import uuid
from math import e
from urllib import response

import requests
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset

from bank.settings import CIRCLE_API

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use logger instead of print statements for better monitoring
logger.info(f"Transaction successful: {response}")
logger.error(f"Error sending USDC to Circle: {e}")

# Circle API and Stellar configuration
STELLAR_SERVER = Server("https://horizon-testnet.stellar.org/")
STELLAR_PUBLIC_KEY = "GCA3RMKZWC7ZHFRBXAPKCWSP3FOWNRRX2NR5K4QZDOKSZVJSA3FSIZKQ"
STELLAR_SECRET_KEY = "SC34UKYKGMAUFWRZNB7ELZDKHJILDMR4SYSKD3B2MEM5YDMGF7US2M3L"
CIRCLE_STELLAR_USDC_ADDRESS = "GAYF33NNNMI2Z6VNRFXQ64D4E4SF77PM46NW3ZUZEEU5X7FCHAZCMHKU"
USDC_ASSET = Asset("USDC", "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5")
CIRCLE_API_URL = "https://api-sandbox.circle.com/v1"
CIRCLE_WALLET_ID = "1017217590"


def generate_idempotency_key():
    return str(uuid.uuid4())


def establish_trustline_for_usdc():
    try:
        account = STELLAR_SERVER.load_account(STELLAR_PUBLIC_KEY)
        keypair = Keypair.from_secret(STELLAR_SECRET_KEY)

        transaction_builder = TransactionBuilder(
            source_account=account,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            base_fee=STELLAR_SERVER.fetch_base_fee()
        )
        # Add Change Trust Operation
        transaction = transaction_builder.append_change_trust_op(
            asset=USDC_ASSET
        ).set_timeout(30).build()

        # Sign and Submit
        transaction.sign(keypair)
        response = STELLAR_SERVER.submit_transaction(transaction)
        print(f"Trustline established: {response}")
        return response
    except Exception as e:
        print(f"Error establishing trustline for USDC: {e}")
        return None


def send_stellar_usdc_to_circle(amount="100"):
    try:
        # Ensure trustline is set up before proceeding
        if not establish_trustline_for_usdc():
            raise Exception("Failed to establish trustline for USDC.")

        account = STELLAR_SERVER.load_account(STELLAR_PUBLIC_KEY)
        keypair = Keypair.from_secret(STELLAR_SECRET_KEY)
        transaction_builder = TransactionBuilder(
            source_account=account,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            base_fee=STELLAR_SERVER.fetch_base_fee()
        )
        # Add Payment Operation
        transaction = transaction_builder.append_payment_op(
            destination=CIRCLE_STELLAR_USDC_ADDRESS,
            asset=USDC_ASSET,
            amount=amount
        ).set_timeout(30).build()

        # Sign and Submit
        transaction.sign(keypair)
        response = STELLAR_SERVER.submit_transaction(transaction)
        print(f"Transaction successful: {response}")
        return response
    except Exception as e:
        print(f"Error sending USDC to Circle: {e}")
        return None


def create_bank_account_recipient(account_number, routing_number):
    url = f"{CIRCLE_API_URL}/transfers/recipients"
    headers = {
        "Authorization": f"Bearer {CIRCLE_API}",
        "Content-Type": "application/json"
    }
    body = {
        "idempotencyKey": "unique_idempotency_key",  # Unique for each request
        "description": "Bank Account Withdrawal",
        "destination": {
            "type": "wire",  # Change to "ach" if using ACH
            "accountNumber": account_number,
            "routingNumber": routing_number,
        }
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 201:
        recipient_id = response.json().get("data")["id"]
        print(f"Bank account recipient created with ID: {recipient_id}")
        return recipient_id
    else:
        print(f"Failed to create bank account recipient: {response.status_code}, {response.text}")
        return None


def initiate_bank_withdrawal(amount, recipient_id):
    url = f"{CIRCLE_API_URL}/payouts"
    headers = {
        "Authorization": f"Bearer {CIRCLE_API}",
        "Content-Type": "application/json"
    }
    body = {
        "idempotencyKey": generate_idempotency_key,  # Unique for each request
        "amount": {
            "amount": amount,
            "currency": "USD"
        },
        "destination": {
            "type": "recipient_id",
            "id": recipient_id
        },
        "source": {
            "type": "wallet",
            "id": CIRCLE_WALLET_ID
        }
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 201:
        transaction_id = response.json().get("data")["id"]
        print(f"Withdrawal initiated, transaction ID: {transaction_id}")
        return transaction_id
    else:
        print(f"Failed to initiate withdrawal: {response.status_code}, {response.text}")
        return None


def confirm_bank_transfer(transaction_id):
    url = f"{CIRCLE_API_URL}/payouts/{transaction_id}"
    headers = {
        "Authorization": f"Bearer {CIRCLE_API}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        transfer_status = response.json().get("data")["status"]
        return transfer_status
    else:
        print(f"Failed to confirm bank transfer: {response.status_code}, {response.text}")
        return None
