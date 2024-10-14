import json
import uuid  # For generating unique idempotency keys
import logging
import requests
from abc import ABC, abstractmethod
from urllib.parse import urljoin
from requests import Timeout
from django.conf import settings
from decimal import Decimal

from app.services.utils import handle_request
from app.supported_countries import SUPPORTED_COUNTRIES


class PaymentGateway(ABC):
    @abstractmethod
    def initiate_deposit(self, amount, account_details, country):
        pass

    @abstractmethod
    def initiate_withdrawal(self, amount, bank_account_id):
        pass

    @abstractmethod
    def supports_country(self, country):
        """Check if the gateway supports a given country"""
        pass

    def link_bank_account(self, account_details):
        """Link the bank account to initiate deposit or withdrawal"""
        headers = self._build_headers()
        data = self._build_bank_account_data(account_details)

        return self._send_post_request("businessAccount/banks/wires", headers, data)

    def _build_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _build_bank_account_data(self, account_details):
        # Ensure account_details is a dictionary (deserialize if it's a JSON string)
        if isinstance(account_details, str):
            try:
                account_details = json.loads(account_details)
            except json.JSONDecodeError:
                return {"error": "Invalid account details format"}

        # Safely extract data using .get() to avoid KeyError
        return {
            "billingDetails": {
                "name": account_details.get('name', 'Unknown'),  # Default to 'Unknown' if key is missing
                "city": account_details.get('city', 'Unknown'),
                "country": account_details.get('country', 'Unknown'),
                "line1": account_details.get('address', 'Unknown'),
                "district": account_details.get('district', 'Unknown'),
                "postalCode": account_details.get('postalCode', 'Unknown')
            },
            "bankAddress": {
                "bankName": account_details.get('bankName', 'Unknown'),
                "city": account_details.get('bankCity', 'Unknown'),
                "country": account_details.get('bankCountry', 'Unknown'),
                "line1": account_details.get('bankAddress', 'Unknown'),
                "district": account_details.get('bankDistrict', 'Unknown')
            },
            "idempotencyKey": self.generate_idempotency_key(),
            "accountNumber": account_details.get('accountNumber', 'Unknown'),
            "routingNumber": account_details.get('routingNumber', 'Unknown')
        }

    def generate_idempotency_key(self):
        # Placeholder function for generating idempotency key
        import uuid
        return str(uuid.uuid4())

    def _send_post_request(self, endpoint, headers, data):
        try:
            response = requests.post(urljoin(self.anchor_url, endpoint), headers=headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Timeout:
            logging.error(f"Request timed out while contacting {endpoint}")
            return {"error": "Request timed out"}
        except requests.HTTPError as e:
            logging.error(f"HTTP error while contacting {endpoint}: {str(e)}")
            return {"error": "HTTP error", "details": str(e)}
        except (ConnectionError, requests.RequestException) as e:
            logging.error(f"Connection error while contacting {endpoint}: {str(e)}")
            return {"error": "Connection error", "details": str(e)}

    @staticmethod
    def generate_idempotency_key():
        """Generate a unique idempotency key"""
        return str(uuid.uuid4())


class CircleGateway(PaymentGateway):
    def __init__(self):
        self.anchor_url = settings.CIRCLE_API_URL
        self.api_key = "SAND_API_KEY:9039b240f6607d4c7d1d255a6f13ab55:21f9777ee2679146da8725287dd90f9e"
        self.asset_code = "USDC"
        self.platform_custody_account = settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT

        if not self.anchor_url or not self.api_key:
            raise ValueError("Circle API URL and API Key must be set in settings.")

    def supports_country(self, country):
        return country in SUPPORTED_COUNTRIES

    def _build_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def initiate_deposit(self, amount, account_details, country):
        if not self.supports_country(country):
            return {"error": "Country not supported for deposits."}

        amount = Decimal(amount)

        account_response = self.link_bank_account(account_details)
        if "error" in account_response:
            return account_response

        transfer_id = account_response.get("data", {}).get("id")
        wire_instructions_response = self.get_wire_instructions(transfer_id)
        if "error" in wire_instructions_response:
            return wire_instructions_response

        wire_instructions = wire_instructions_response.get("data")
        return self.make_deposit(amount, wire_instructions)

    def get_wire_instructions(self, transfer_id):
        headers = self._build_headers()
        url = urljoin(self.anchor_url, f"/v1/businessAccount/banks/wires/{transfer_id}/instructions")
        params = {"currency": "USD"}

        logging.debug(f"Requesting wire instructions from {url} with headers: {headers}")
        logging.debug(f"Request params: {params}")

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            logging.debug(f"Response status code: {response.status_code}")
            logging.debug(f"Response content: {response.text}")

            response.raise_for_status()
            return response.json()
        except Timeout:
            logging.error("Request timed out while fetching wire instructions.")
            return {"error": "Request timed out"}
        except requests.HTTPError as e:
            logging.error(f"HTTP error occurred while fetching wire instructions: {str(e)}")
            logging.error(f"Response content: {e.response.text}")
            return {"error": "HTTP error", "details": str(e), "response_content": e.response.text}
        except Exception as e:
            logging.error(f"Unexpected error occurred while fetching wire instructions: {str(e)}")
            return {"error": "Unexpected error", "details": str(e)}

    def make_deposit(self, amount, wire_instructions):
        headers = self._build_headers()
        data = {
            "asset_code": self.asset_code,
            "account": wire_instructions['beneficiaryBank']['accountNumber'],
            "amount": str(amount)
        }

        return handle_request(
            requests.post,
            urljoin(self.anchor_url, "/transactions/deposit/interactive"),
            headers=headers,
            json=data,
            timeout=10
        )

    """def transfer_usdc_to_custody_account(self, amount):
        # Send USDC to custody Stellar account
        stellar_response = self.stellar_service.transfer_usdc(amount, self.platform_custody_account)
        if "error" in stellar_response:
            logging.error(f"Failed to transfer USDC to custody: {stellar_response['error']}")
        else:
            logging.info(f"Successfully transferred {amount} USDC to custody account: {self.platform_custody_account}")"""

    # Similar improvements for withdrawal
    def initiate_withdrawal(self, amount, bank_account_id):
        stellar_withdrawal_response = self.withdraw_from_stellar(amount)
        if "error" in stellar_withdrawal_response:
            return stellar_withdrawal_response
        return self.process_circle_payout(amount, bank_account_id)

    def withdraw_from_stellar(self, amount):
        destination_address = settings.CIRCLE_USDC_ADDRESS
        try:
            response = self.stellar_service.send_payment(destination=destination_address, amount=amount)
            return response if 'error' not in response else {"error": "Failed Stellar withdrawal",
                                                             "details": response['error']}
        except Exception as e:
            logging.error(f"Stellar withdrawal error: {str(e)}")
            return {"error": "Stellar withdrawal error", "details": str(e)}

    def process_circle_payout(self, amount, bank_account_id):
        headers = self._build_headers()
        data = {
            "destination": {"type": "wire", "id": bank_account_id},
            "amount": {"currency": "USD", "amount": str(amount)},
            "idempotencyKey": self.generate_idempotency_key(),
        }
        try:
            response = requests.post(
                urljoin(self.anchor_url, "/businessAccount/payouts"),
                headers=headers, json=data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except (Timeout, ConnectionError, requests.RequestException) as e:
            logging.error(f"Error during withdrawal: {str(e)}")
            return {"error": "Request failed", "details": str(e)}


"""class LinkioGateway(PaymentGateway):
    def __init__(self):
        self.anchor_url = settings.LINKIO_API_URL
        self.linkio_api_key = settings.LINKIO_API_KEY
        self.asset_code = "USDC"  # Or any other supported currency

        if not self.anchor_url or not self.linkio_api_key:
            raise ValueError("Linkio API URL and API Key must be set in settings.")

    def supports_country(self, country):
        return country in SUPPORTED_COUNTRIES

    def initiate_deposit(self, amount, account, country):
        if not self.supports_country(country):
            return {"error": "Country not supported for deposits."}

        headers = {
            "Authorization": f"Bearer {self.linkio_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "asset_code": self.asset_code,
            "account": account,
            "amount": str(amount)
        }

        try:
            response = requests.post(
                urljoin(self.anchor_url, "/transactions/deposit/interactive"),
                headers=headers, json=data, timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error initiating deposit with Linkio: {response.text}")
                return {"error": "Failed to initiate deposit", "details": response.text}

        except Timeout:
            logging.error("Request timed out")
            return {"error": "Request timed out"}
        except ConnectionError:
            logging.error("Connection error occurred")
            return {"error": "Connection error"}
        except requests.RequestException as e:
            logging.error(f"Request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}

    def initiate_withdrawal(self, amount, account, country):
        if not self.supports_country(country):
            return {"error": "Country not supported for withdrawals."}

        headers = {
            "Authorization": f"Bearer {self.linkio_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "asset_code": self.asset_code,
            "account": account,
            "amount": decimal.Decimal(amount)
        }

        try:
            response = requests.post(
                urljoin(self.anchor_url, "/transactions/withdraw/interactive"),
                headers=headers, json=data, timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error initiating withdrawal with Linkio: {response.text}")
                return {"error": "Failed to initiate withdrawal", "details": response.text}

        except Timeout:
            logging.error("Request timed out")
            return {"error": "Request timed out"}
        except ConnectionError:
            logging.error("Connection error occurred")
            return {"error": "Connection error"}
        except requests.RequestException as e:
            logging.error(f"Request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}"""
