import requests
from django.conf import settings

from app.models import logger, LinkedAccount, User
from app.services.stellar_network_service import process_stellar_to_circle_withdrawal
from app.services.transact.withdrawal_utils import get_user_virtual_balance


def get_user_bank_account_id(user, account_id=None):
    """Fetches the bank account ID for the user from the LinkedAccount model.

    :param user: ID of the user
    :param account_id: Optional specific account ID to fetch
    """
    try:
        if account_id:
            linked_account = LinkedAccount.objects.filter(user=user, id=account_id).first()
            if linked_account:
                return linked_account.bank_account_id
            else:
                logger.error(f"Linked account {account_id} not found for user {user}")
                raise ValueError("Specified linked account not found")
        else:
            # Default behavior: return the first linked account
            linked_account = LinkedAccount.objects.filter(user=user).first()
            if linked_account:
                return linked_account.bank_account_id
            else:
                logger.error(f"No linked bank account found for user {user}")
                raise ValueError("User does not have a linked bank account")

    except User.DoesNotExist:
        logger.error(f"User {user} not found")
        raise ValueError("User not found")


class CircleAPI:
    BASE_URL = "https://sandbox-api.circle.com/v1"  # Replace with the correct Circle API base URL
    HEADERS = {
        "Authorization": settings.CIRCLE_API,  # Replace with your actual API key
        "Content-Type": "application/json"
    }

    @staticmethod
    def create_payout(payout_data):
        """Creates a payout request via Circle API."""
        try:
            url = f"{CircleAPI.BASE_URL}/payouts"  # Assuming this is the correct endpoint
            response = requests.post(url, headers=CircleAPI.HEADERS, json=payout_data)
            response.raise_for_status()  # Raises an error for HTTP error responses
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {str(http_err)}")
            return {"error": f"HTTP error occurred: {str(http_err)}"}
        except Exception as e:
            logger.error(f"Error creating Circle payout: {str(e)}")
            return {"error": f"Error creating Circle payout: {str(e)}"}


def process_withdrawal(user, withdrawal_amount):
    """Main method to handle withdrawal from Stellar and create Circle payout."""
    # Step 1: Validate user balance
    user_balance = get_user_virtual_balance(user)
    if user_balance < withdrawal_amount:
        raise ValueError("Insufficient funds in Stellar account.")

    # Step 2: Withdraw from Stellar
    stellar_withdrawal_response = process_stellar_to_circle_withdrawal(user, withdrawal_amount)

    if stellar_withdrawal_response != "success":
        raise ValueError("Withdrawal from Stellar failed: " + stellar_withdrawal_response)

    # Step 3: Prepare payout data for Circle
    payout_data = {
        "amount": withdrawal_amount,
        "currency": "USD",
        "recipient": {
            "bank_account_id": get_user_bank_account_id(user),  # Fetch the bank account ID
            "type": "ACH"  # or "wire" depending on the type of transfer
        },
        "description": "Withdrawal to bank account"
    }

    # Step 4: Create Circle payout
    circle_response = CircleAPI.create_payout(payout_data)
    if "error" in circle_response:
        raise ValueError("Circle payout creation failed: " + circle_response["error"])

    return circle_response  # Return response from Circle API
