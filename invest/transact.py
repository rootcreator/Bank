import requests
from django.conf import settings


# Sending funds from Stellar to Portfolio (Circle API)
def send_funds_from_stellar(amount, user):
    url = f"{settings.CIRCLE_API_URL}/transfers"
    headers = {
        "Authorization": f"Bearer {settings.CIRCLE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "source": {
            "type": "stellar",  # Assuming using Stellar as the blockchain
            "user_id": user.id
        },
        "destination": {
            "type": "portfolio",
            "portfolio_id": user.portfolio.alpaca_account_id  # Portfolio account ID
        },
        "amount": amount,
        "currency": "USD"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return {"success": True}
    else:
        return {"success": False, "error": response.json().get('error')}


# Withdrawing funds from Portfolio to Stellar (Circle API)
def withdraw_funds_to_stellar(amount, user):
    url = f"{settings.CIRCLE_API_URL}/transfers"
    headers = {
        "Authorization": f"Bearer {settings.CIRCLE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "source": {
            "type": "portfolio",
            "portfolio_id": user.portfolio.alpaca_account_id
        },
        "destination": {
            "type": "stellar",  # Sending back to Stellar wallet
            "user_id": user.id
        },
        "amount": amount,
        "currency": "USD"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return {"success": True}
    else:
        return {"success": False, "error": response.json().get('error')}
