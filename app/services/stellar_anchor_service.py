import logging
import requests
from urllib.parse import urljoin
from django.conf import settings
from rest_framework.authtoken.models import Token
from app.models import Transaction


class StellarAnchorService:
    def __init__(self):
        self.anchor_url = settings.ANCHOR_URL  # e.g., "https://api.circle.com/v1"
        self.asset_code = "USDC"
        self.circle_api_key = settings.CIRCLE_API_KEY

    def initiate_deposit(self, user, amount):
        token = Token.objects.get(user=user).key
        headers = {
            "Authorization": f"Bearer {self.circle_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "asset_code": self.asset_code,
            "account": settings.STELLAR_PLATFORM_PUBLIC_KEY,  # Use public key directly from settings
            "amount": str(amount)
        }
        try:
            response = requests.post(urljoin(self.anchor_url, "/transactions/deposit/interactive"), headers=headers,
                                     json=data, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error initiating deposit: {response.text}")
                return {"error": "Failed to initiate deposit", "details": response.text}
        except requests.RequestException as e:
            logging.error(f"Request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}

    def initiate_withdrawal(self, user, amount):
        token = Token.objects.get(user=user).key
        headers = {
            "Authorization": f"Bearer {self.circle_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "asset_code": self.asset_code,
            "account": settings.STELLAR_PLATFORM_PUBLIC_KEY,  # Use public key directly from settings
            "amount": str(amount)
        }
        try:
            response = requests.post(urljoin(self.anchor_url, "/transactions/withdraw/interactive"), headers=headers,
                                     json=data, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error initiating withdrawal: {response.text}")
                return {"error": "Failed to initiate withdrawal", "details": response.text}
        except requests.RequestException as e:
            logging.error(f"Request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}

    def check_transaction_status(self, transaction_id):
        response = requests.get(urljoin(self.anchor_url, f"/transactions/{transaction_id}"))
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": "Failed to check transaction status", "details": response.text}

    @staticmethod
    def process_anchor_callback(callback_data):
        transaction_id = callback_data.get('transaction_id')
        status = callback_data.get('status')

        transaction = Transaction.objects.filter(external_transaction_id=transaction_id).first()

        if transaction:
            if status == 'completed':
                transaction.status = 'completed'
                transaction.save()
                # Update user's USD account or perform other actions as necessary
            elif status == 'failed':
                transaction.status = 'failed'
                transaction.save()
                # Handle any necessary refund logic
        else:
            return {"error": "Transaction not found"}
