import requests
from .config import RELOADLY_API_KEY, RELOADLY_BASE_URL


class ReloadlyService:
    def __init__(self):
        self.base_url = RELOADLY_BASE_URL
        self.headers = {
            'Authorization': f'Bearer {RELOADLY_API_KEY}',
            'Content-Type': 'application/json',
        }

    def top_up(self, amount, recipient, currency):
        url = f"{self.base_url}/topups"
        payload = {
            "amount": amount,
            "recipient": recipient,
            "currency": currency,
        }

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error {response.status_code}: {response.text}")

    def get_gift_cards(self):
        url = f"{self.base_url}/gift-cards"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error {response.status_code}: {response.text}")

    # Additional methods can be added as needed (e.g., for gift card purchases)
