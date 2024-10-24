import time
import uuid

import requests
from django.conf import settings

from app.models import logger, LinkedAccount, User


class CircleAPI:
    BASE_URL = "https://api-sandbox.circle.com/v1"  # Use production URL in live environment
    BANK_ACCOUNT_CREATE_URL = f"{BASE_URL}/banks/wires"
    HEADERS = {
        "Authorization": f"Bearer {settings.CIRCLE_API}",  # Ensure secure storage
        "Content-Type": "application/json"
    }

    MAX_RETRIES = 3  # Retry limit for transient network failures
    RETRY_BACKOFF = 2  # Exponential backoff factor

    @staticmethod
    def create_payout(payout_data):
        """Creates a payout request via Circle API with retry logic."""
        attempt = 0
        while attempt < CircleAPI.MAX_RETRIES:
            try:
                url = f"{CircleAPI.BASE_URL}/payouts"
                response = requests.post(url, headers=CircleAPI.HEADERS, json=payout_data)
                response.raise_for_status()  # Raise error for HTTP error responses
                return response.json()
            except requests.exceptions.HTTPError as http_err:
                logger.error(f"HTTP error during Circle payout: {http_err.response.text}")
                return {"error": f"HTTP error occurred: {http_err.response.text}"}
            except requests.exceptions.RequestException as req_err:
                logger.error(f"Network error during Circle payout: {str(req_err)}")
                attempt += 1
                if attempt < CircleAPI.MAX_RETRIES:
                    time.sleep(CircleAPI.RETRY_BACKOFF ** attempt)  # Exponential backoff with retries
                else:
                    return {"error": "Network error. Please try again later."}
            except Exception as e:
                logger.error(f"Unexpected error during Circle payout: {str(e)}")
                return {"error": "An unexpected error occurred. Please try again later."}


def get_user_bank_account_id(user, account_number=None, transfer_type='wire'):
    """
    Fetches the bank account ID for the user from the LinkedAccount model.
    :param user: User object
    :param account_number: Optional specific account number to fetch
    :param transfer_type: Type of transfer (e.g., 'wire', 'ACH')
    :return: Bank account ID associated with the user or None
    :raises ValueError: If the user or account is not found or invalid
    """
    try:
        linked_accounts = LinkedAccount.objects.filter(user=user)

        if not linked_accounts.exists():
            logger.error(f"No linked bank account found for user {user.id}")
            return None

        if account_number:
            # Fetch specific account by account number
            linked_account = linked_accounts.filter(account_number=account_number).first()
            if linked_account:
                return linked_account.bank_account_id
            else:
                logger.error(f"Account {account_number} not found for user {user.id}")
                return None
        else:
            # Fetch default/first account if no account_number is specified
            linked_account = linked_accounts.first()

            # Validate the transfer type compatibility
            if transfer_type.lower() not in ['wire', 'ach']:
                logger.error(f"Unsupported transfer type {transfer_type} for user {user.id}")
                return None

            return linked_account.bank_account_id

    except User.DoesNotExist:
        logger.error(f"User {user.id} not found")
        return None


def generate_unique_idempotency_key():
    """Generates a unique idempotency key using UUID."""
    return str(uuid.uuid4())  # UUID for idempotency key



