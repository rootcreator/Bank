import uuid  # For generating unique idempotency keys

import logging
import requests
from abc import ABC, abstractmethod
from urllib.parse import urljoin
from requests import Timeout
from django.conf import settings
from app.supported_countries import SUPPORTED_COUNTRIES


class PaymentGateway(ABC):
    @abstractmethod
    def initiate_deposit(self, amount, account, country):
        pass

    @abstractmethod
    def initiate_withdrawal(self, amount, account, country):
        pass

    @abstractmethod
    def supports_country(self, country):
        """Check if the gateway supports a given country"""
        pass

    def link_bank_account(self, account_details):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            # build data as per subclass specifics
        }
        return self._send_post_request("/businessAccount/banks/wires", headers, data)

    def _send_post_request(self, endpoint, headers, data):
        try:
            response = requests.post(urljoin(self.anchor_url, endpoint), headers=headers, json=data, timeout=10)
            response.raise_for_status()  # Raises HTTPError for bad responses
            return response.json()
        except (Timeout, ConnectionError) as e:
            logging.error(f"Connection error occurred: {str(e)}")
            return {"error": "Connection error", "details": str(e)}
        except requests.HTTPError as e:
            logging.error(f"HTTP error occurred: {str(e)}")
            return {"error": "HTTP error", "details": str(e)}


class CircleGateway(PaymentGateway):
    def __init__(self):
        self.anchor_url = settings.CIRCLE_API_URL
        self.api_key = settings.CIRCLE_API_KEY
        self.asset_code = "USDC"
self.platform_custody_account = settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT  # Add your custody Stellar account here

        if not self.anchor_url or not self.api_key:
            raise ValueError("Circle API URL and API Key must be set in settings.")

    def supports_country(self, country):
        return country in SUPPORTED_COUNTRIES

    def initiate_deposit(self, amount, account_details, country):
        if not self.supports_country(country):
            return {"error": "Country not supported for deposits."}

        account_response = self.link_bank_account(account_details)
        if "error" in account_response:
            return account_response

        # Step 2: Get wire instructions
        transfer_id = account_response.get("data", {}).get("id")
        wire_instructions_response = self.get_wire_instructions(transfer_id)
        if "error" in wire_instructions_response:
            return wire_instructions_response

        # Step 3: Initiate the deposit
        wire_instructions = wire_instructions_response.get("data")
        deposit_response = self.make_deposit(amount, wire_instructions)
        return deposit_response

    def link_bank_account(self, account_details):
        headers = {
            "Authorization": f"Bearer {self.circle_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "billingDetails": {
                "name": account_details['name'],
                "city": account_details['city'],
                "country": account_details['country'],
                "line1": account_details['address'],
                "district": account_details['district'],
                "postalCode": account_details['postalCode']
            },
            "bankAddress": {
                "bankName": account_details['bankName'],
                "city": account_details['bankCity'],
                "country": account_details['bankCountry'],
                "line1": account_details['bankAddress'],
                "district": account_details['bankDistrict']
            },
            "idempotencyKey": "unique-key",  # Generate a unique key here
            "accountNumber": account_details['accountNumber'],
            "routingNumber": account_details['routingNumber']
        }

        try:
            response = requests.post(
                urljoin(self.anchor_url, "/v1/businessAccount/banks/wires"),
                headers=headers, json=data, timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error linking bank account: {response.text}")
                return {"error": "Failed to link bank account", "details": response.text}

        except (Timeout, ConnectionError) as e:
            logging.error(f"Connection error occurred: {str(e)}")
            return {"error": "Connection error", "details": str(e)}

    def get_wire_instructions(self, transfer_id):
        headers = {
            "Authorization": f"Bearer {self.circle_api_key}"
        }
        try:
            response = requests.get(
                urljoin(self.anchor_url, f"/v1/businessAccount/banks/wires/{transfer_id}/instructions?currency=USD"),
                headers=headers, timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error retrieving wire instructions: {response.text}")
                return {"error": "Failed to retrieve wire instructions", "details": response.text}

        except (Timeout, ConnectionError) as e:
            logging.error(f"Connection error occurred: {str(e)}")
            return {"error": "Connection error", "details": str(e)}




    def make_deposit(self, amount, wire_instructions):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "asset_code": self.asset_code,
            "account": wire_instructions['beneficiaryBank']['accountNumber'],
            "amount": amount
        }

        try:
            response = requests.post(
                urljoin(self.anchor_url, "/transactions/deposit/interactive"),
                headers=headers, json=data, timeout=10
            )

            if response.status_code == 200:
                response_data = response.json()
                minted_usdc_amount = response_data.get('amount')  # Adjust this according to your API response structure
                # Now transfer USDC to the custody Stellar account
                self.transfer_usdc_to_custody_account(minted_usdc_amount)
                return response_data
            else:
                logging.error(f"Error initiating deposit with Circle: {response.text}")
                return {"error": "Failed to initiate deposit", "details": response.text}

        except (Timeout, ConnectionError) as e:
            logging.error(f"Connection error occurred: {str(e)}")
            return {"error": "Connection error", "details": str(e)}

    def transfer_usdc_to_custody_account(self, amount):
        # Logic to send USDC to the custody Stellar account
        # Use Stellar SDK or your existing Stellar service to implement this
        stellar_response = self.stellar_service.transfer_usdc(amount, self.platform_custody_account)
        if "error" in stellar_response:
            logging.error(f"Failed to transfer USDC to custody Stellar account: {stellar_response['error']}")
        else:
            logging.info(f"Successfully transferred {amount} USDC to custody Stellar account: {self.platform_custody_account}")
   



 # Withdraw

    def link_bank_account(self, billing_details, bank_address, account_number, routing_number):
        headers = {
            "Authorization": f"Bearer {self.circle_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "billingDetails": billing_details,
            "bankAddress": bank_address,
            "idempotencyKey": "some-unique-key-here",  # Generate a unique key for idempotency
            "accountNumber": account_number,
            "routingNumber": routing_number
        }

        url = urljoin(self.anchor_url, "/businessAccount/banks/wires")
        logging.info(f"Linking bank account with request data: {data}")

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error linking bank account: {response.status_code} {response.text}")
                return {"error": "Failed to link bank account", "details": response.text}

        except (Timeout, ConnectionError, requests.RequestException) as e:
            logging.error(f"Error during bank account linking: {str(e)}")
            return {"error": "Request failed", "details": str(e)}



    def initiate_withdrawal(self, amount, bank_account_id):
        headers = {
            "Authorization": f"Bearer {self.circle_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "destination": {
                "type": "wire",
                "id": bank_account_id
            },
            "amount": {
                "currency": "USD",
                "amount": str(amount)
            },
            "idempotencyKey": "some-unique-key-here",  # Generate a unique key for idempotency
        }

        url = urljoin(self.anchor_url, "/businessAccount/payouts")
        logging.info(f"Sending withdrawal request to {url} with data: {data}")

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error initiating withdrawal: {response.status_code} {response.text}")
                return {"error": "Failed to initiate withdrawal", "details": response.text}

        except (Timeout, ConnectionError, requests.RequestException) as e:
            logging.error(f"Error during withdrawal: {str(e)}")
            return {"error": "Request failed", "details": str(e)}

    def check_withdrawal_status(self, payout_id):
        headers = {
            "Authorization": f"Bearer {self.circle_api_key}",
            "accept": "application/json"
        }

        url = urljoin(self.anchor_url, f"/businessAccount/payouts/{payout_id}")
        logging.info(f"Checking withdrawal status for payout ID: {payout_id}")

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error checking withdrawal status: {response.status_code} {response.text}")
                return {"error": "Failed to check withdrawal status", "details": response.text}

        except (Timeout, ConnectionError, requests.RequestException) as e:
            logging.error(f"Error during status check: {str(e)}")
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

