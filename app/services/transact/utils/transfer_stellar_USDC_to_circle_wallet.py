import logging
import uuid
from decimal import Decimal
from typing import Optional

import requests
from django.shortcuts import get_object_or_404
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset

from app.models import LinkedAccount
from bank.settings import CIRCLE_API

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Circle API and Stellar configuration
STELLAR_SERVER = Server("https://horizon-testnet.stellar.org/")
CIRCLE_API_URL = "https://api-sandbox.circle.com/v1"
STELLAR_PUBLIC_KEY = "GCA3RMKZWC7ZHFRBXAPKCWSP3FOWNRRX2NR5K4QZDOKSZVJSA3FSIZKQ"
STELLAR_SECRET_KEY = "SC34UKYKGMAUFWRZNB7ELZDKHJILDMR4SYSKD3B2MEM5YDMGF7US2M3L"
CIRCLE_STELLAR_USDC_ADDRESS = "GAYF33NNNMI2Z6VNRFXQ64D4E4SF77PM46NW3ZUZEEU5X7FCHAZCMHKU"
USDC_ASSET = Asset("USDC", "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5")
CIRCLE_WALLET_ID = "1017217590"
headers = {
    "Authorization": CIRCLE_API,  # Use actual API key
    "Content-Type": "application/json"
}


def generate_idempotency_key():
    return str(uuid.uuid4())


class CircleWithdrawalProvider:
    """Circle implementation of withdrawal provider with external bank account support"""

    PAYOUT_ENDPOINT = "businessAccount/payouts"
    REQUEST_TIMEOUT = 30

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or CIRCLE_API
        self.base_url = base_url or CIRCLE_API_URL

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def create_bank_withdrawal(self, bank_details, amount, currency, billing_details):
        """
        Process a bank withdrawal with provided bank account details
        """
        try:
            amount_decimal = Decimal(str(amount))
            destination_data = self._prepare_bank_destination_data(bank_details, billing_details)

            response = requests.post(
                f"{self.base_url}/{self.PAYOUT_ENDPOINT}",
                json={
                    "destination": destination_data,
                    "amount": {"amount": str(amount_decimal), "currency": currency},
                    "idempotencyKey": str(uuid.uuid4()),
                },
                headers=self.headers,
                timeout=self.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Circle API request failed: {str(e)}")
            return None

    @staticmethod
    def _prepare_bank_destination_data(bank_details, billing_details):
        """
        Prepare bank account data for Circle API
        """
        destination_data = {
            'type': 'wire',
            'billingDetails': {
                'name': bank_details['account_holder_name'],
                'city': billing_details.get('city', ''),
                'country': billing_details.get('country', ''),
                'line1': billing_details.get('address', ''),
                'district': billing_details.get('state', ''),
                'postalCode': billing_details.get('postal_code', '')
            },
            'accountNumber': bank_details['account_number'],
            'routingNumber': bank_details['routing_number']
        }
        return destination_data


# Step 1: Establish Stellar Trustline
def establish_trustline_for_usdc():
    try:
        account = STELLAR_SERVER.load_account(STELLAR_PUBLIC_KEY)
        keypair = Keypair.from_secret(STELLAR_SECRET_KEY)

        transaction_builder = TransactionBuilder(
            source_account=account,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            base_fee=STELLAR_SERVER.fetch_base_fee()
        )
        transaction = transaction_builder.append_change_trust_op(
            asset=USDC_ASSET
        ).set_timeout(30).build()

        transaction.sign(keypair)
        response = STELLAR_SERVER.submit_transaction(transaction)
        return response
    except Exception as e:
        logger.error(f"Error establishing trustline for USDC: {e}")
        return None


# Step 2: Send USDC to Circle on Stellar
def send_stellar_usdc_to_circle(amount="100"):
    try:
        if not establish_trustline_for_usdc():
            raise Exception("Failed to establish trustline for USDC.")

        account = STELLAR_SERVER.load_account(STELLAR_PUBLIC_KEY)
        keypair = Keypair.from_secret(STELLAR_SECRET_KEY)
        transaction_builder = TransactionBuilder(
            source_account=account,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            base_fee=STELLAR_SERVER.fetch_base_fee()
        )
        transaction = transaction_builder.append_payment_op(
            destination=CIRCLE_STELLAR_USDC_ADDRESS,
            asset=USDC_ASSET,
            amount=amount
        ).set_timeout(30).build()

        transaction.sign(keypair)
        response = STELLAR_SERVER.submit_transaction(transaction)
        logger.info(f"Transaction successful: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending USDC to Circle: {e}")
        return None


# Step 3: Process Circle Bank Withdrawal
def process_circle_withdrawal(bank_details, billing_details, amount, currency):
    try:
        circle_withdrawal_provider = CircleWithdrawalProvider()
        result = circle_withdrawal_provider.create_bank_withdrawal(
            bank_details=bank_details,
            amount=amount,
            currency=currency,
            billing_details=billing_details
        )
        if result:
            logger.info(f"Withdrawal successful: {result}")
        else:
            logger.error("Failed to process Circle withdrawal.")
    except Exception as e:
        logger.error(f"Error during Circle withdrawal: {e}")


"""def create_bank_account_recipient(account_holder_name: str, account_number: str, routing_number: str, billing_address: dict) -> dict:
    url = f"{CIRCLE_API_URL}/businessAccount/banks/wires"
    headers = {
        "Authorization": f"Bearer {CIRCLE_API}",
        "Content-Type": "application/json"
    }
    body = {
        "idempotencyKey": generate_idempotency_key(),
        "description": f"Bank account for {account_holder_name}",
        "destination": {
            "type": "wire",
            "accountNumber": account_number,
            "routingNumber": routing_number,
        },
        "billingDetails": billing_address
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 201:
        logger.info(f"Bank account recipient created: {response.json()}")
        return response.json()
    else:
        logger.error(f"Failed to create bank account recipient: {response.status_code}, {response.text}")
        return {}"""


def create_bank_account_recipient(bank_details):
    """
    Links a bank account in Circle using the provided bank details.

    Args:
        bank_details (dict): A dictionary containing the bank account information,
            e.g., {"accountNumber": "1234567890", "routingNumber": "012345678", ...}

    Returns:
        str: The Circle ID of the newly linked bank account.
    """

    # Replace with the actual Circle API endpoint for linking bank accounts
    circle_api_url = "https://api.circle.com/v1/bank-accounts"

    # Prepare the request data using the bank details
    data = {
        "accountType": "CHECKING",  # or "SAVINGS"
        "accountNumber": bank_details["account_number"],
        "routingNumber": bank_details["routing_number"],
        "accountHolderName": bank_details["accountHolderName"],
        "accountHolderType": "INDIVIDUAL",  # or "BUSINESS"
        "currency": "USD",
        "bankName": bank_details.get("bankName", ""),  # Optional
        "bankAddress": {
            "street": bank_details.get("bankAddress", {}).get("street", ""),
            "city": bank_details.get("bankAddress", {}).get("city", ""),
            "state": bank_details.get("bankAddress", {}).get("state", ""),
            "postalCode": bank_details.get("bankAddress", {}).get("postalCode", ""),
            "country": bank_details.get("bankAddress", {}).get("country", "")
        },
        "billingAddress": {
            "street": bank_details.get("billingAddress", {}).get("street", ""),
            "city": bank_details.get("billingAddress", {}).get("city", ""),
            "state": bank_details.get("billingAddress", {}).get("state", ""),
            "postalCode": bank_details.get("billingAddress", {}).get("postalCode", ""),
            "country": bank_details.get("billingAddress", {}).get("country", "")
        }
    }

    # Set the necessary headers, including your Circle API key
    headers = {
        "Authorization": "Bearer YOUR_API_KEY",
        "Content-Type": "application/json"
    }

    try:
        # Log the data being sent for debugging
        logger.info(f"Data sent to Circle API: {data}")

        # Send the POST request to Circle's API
        response = requests.post(circle_api_url, json=data, headers=headers)

        # Log the response for debugging
        logger.info(f"Response from Circle: {response.status_code} - {response.text}")

        # Handle the response based on the status code
        if response.status_code == 201:
            bank_account_circle_id = response.json()["id"]
            return bank_account_circle_id
        else:
            raise Exception(f"Circle API returned an error: {response.json()}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        raise
    except KeyError as e:
        logger.error(f"Missing key in data dictionary: {e}")
        raise


"""def initiate_bank_withdrawal(amount, recipient_id):
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
        return None"""


def initiate_bank_withdrawal(user, amount, bank_account_id=None, bank_details=None):
    """
        Initiates a payout to the user by linking a bank account or selecting an existing one.
        Params:
            - user: The user making the request
            - amount: The amount to be transferred
            - bank_account_id: (Optional) ID of an already linked bank account
            - bank_details: (Optional) New bank details if the account is being linked for the first time.
                            Should be a dict with accountNumber, routingNumber, etc.
        """

    # Step 1: Fetch or link a bank account
    if bank_account_id:
        # Fetch existing bank account from the LinkedAccount model
        linked_account = get_object_or_404(LinkedAccount, id=bank_account_id, user=user)
        bank_account_circle_id = linked_account.circle_bank_account_id  # ID stored after account is linked in Circle
    elif bank_details:
        # Link a new bank account using Circle API (Assuming there’s a separate API for linking)
        bank_account_circle_id = create_bank_account_recipient(bank_details)
    else:
        raise ValueError("Either a bank account ID or bank details must be provided.")

    # Step 2: Create the payout request data
    data = {
        "amount": {
            "currency": "USD",
            "amount": str(amount)
        },
        "trackingRef": f"payout-{user.id}-{amount}",  # Unique reference per user transaction
        "destination": {
            "type": "bank-account",
            "id": bank_account_circle_id
        }
    }

    try:
        # Step 3: Send the payout request
        response = requests.post(CIRCLE_API_URL, json=data, headers=headers)

        # Step 4: Error handling based on the response status
        if response.status_code == 201:
            return response.json()  # Payout successful
        elif response.status_code == 400:
            raise Exception("Bad request. Check the input data.")
        elif response.status_code == 401:
            raise Exception("Unauthorized. Invalid API key.")
        elif response.status_code == 404:
            raise Exception("Bank account not found.")
        else:
            raise Exception(f"An error occurred: {response.text}")

    except requests.exceptions.RequestException as e:
        # Handle network-related errors
        raise Exception(f"Network error: {e}")


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
