import logging

import requests
from requests import Timeout

from app.models import Fee
from decimal import Decimal


def calculate_fee(transaction_type, amount):
    total_amount, fee_amount = Fee.apply_transaction_fee(transaction_type, amount)
    net_amount = Decimal(amount) - fee_amount
    return total_amount, fee_amount, net_amount


def has_sufficient_balance(account, amount):
    return account.balance >= amount


def handle_request(request_func, *args, **kwargs):
    try:
        response = request_func(*args, **kwargs)
        response.raise_for_status()
        return response.json()
    except Timeout:
        logging.error(f"Request timed out for {request_func.__name__}")
        return {"error": "Request timed out"}
    except requests.HTTPError as e:
        logging.error(f"HTTP error: {str(e)}")
        return {"error": "HTTP error", "details": str(e)}
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return {"error": "Unexpected error", "details": str(e)}