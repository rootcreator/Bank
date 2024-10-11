from abc import ABC, abstractmethod
import requests
import logging
from urllib.parse import urljoin
from django.conf import settings
from requests import Timeout


class PaymentGateway(ABC):
    @abstractmethod
    def initiate_deposit(self, amount, account):
        pass

    @abstractmethod
    def initiate_withdrawal(self, amount, account):
        pass

    @abstractmethod
    def supports_country(self, country):
        """Check if the gateway supports a given country"""
        pass


class CircleGateway(PaymentGateway):
    SUPPORTED_COUNTRIES = ['US', 'GB', 'CA', 'DE', 'FR']

    def __init__(self):
        self.anchor_url = settings.CIRCLE_API_URL
        self.circle_api_key = settings.CIRCLE_API_KEY
        self.asset_code = "USDC"

        # Check that essential settings are configured
        if not self.anchor_url or not self.circle_api_key:
            raise ValueError("Circle API URL and API Key must be set in settings.")

    def supports_country(self, country):
        return country in self.SUPPORTED_COUNTRIES

    def initiate_deposit(self, amount, account, country):
        if not self.supports_country(country):
            return {"error": "Country not supported for deposits."}

        headers = {
            "Authorization": f"Bearer {self.circle_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "asset_code": self.asset_code,
            "account": account,
            "amount": str(amount)
        }

        try:
            response = requests.post(urljoin(self.anchor_url, "/transactions/deposit/interactive"),
                                     headers=headers, json=data, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error initiating deposit with Circle: {response.text}")
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
            "Authorization": f"Bearer {self.circle_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "asset_code": self.asset_code,
            "account": account,
            "amount": str(amount)
        }

        try:
            response = requests.post(urljoin(self.anchor_url, "/transactions/withdraw/interactive"),
                                     headers=headers, json=data, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Error initiating withdrawal with Circle: {response.text}")
                return {"error": "Failed to initiate withdrawal", "details": response.text}

        except Timeout:
            logging.error("Request timed out")
            return {"error": "Request timed out"}
        except ConnectionError:
            logging.error("Connection error occurred")
            return {"error": "Connection error"}
        except requests.RequestException as e:
            logging.error(f"Request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}



class LinkioGateway(PaymentGateway):
    def __init__(self):
        self.anchor_url = settings.LINKIO_API_URL
        self.linkio_api_key = settings.LINKIO_API_KEY
        self.asset_code = "USDC"  # Or any other supported currency

        if not self.anchor_url or not self.linkio_api_key:
            raise ValueError("Linkio API URL and API Key must be set in settings.")

    def supports_country(self, country):
        # Update with the supported countries from Linkio's documentation
        SUPPORTED_COUNTRIES = ['US', 'NG', 'GB', 'CA', 'BR']
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
            "amount": str(amount)
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
            return {"error": "Request failed", "details": str(e)}

