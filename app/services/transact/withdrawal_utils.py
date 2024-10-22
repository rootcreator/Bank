import logging
import re
import uuid

import requests
from django.conf import settings
from django.db import transaction
from stellar_sdk import Server, Keypair, TransactionBuilder, Network

from app.models import User, LinkedAccount, USDAccount, Beneficiary

logger = logging.getLogger(__name__)


def get_user_virtual_balance(user):
    """
    Fetch the user's virtual balance from the USDAccount model.
    """
    try:
        # Retrieve the USDAccount for the given user
        account = USDAccount.objects.get(user=user)
        return account.balance
    except USDAccount.DoesNotExist:
        raise ValueError(f"User with ID {user} does not have a USD account")


@transaction.atomic
def update_user_virtual_balance(user, withdrawal_amount):
    """
    Update the user's virtual balance after a successful withdrawal.
    Deduct the withdrawal_amount from the user's balance.
    """
    try:
        # Retrieve the user's account and perform the balance update
        account = USDAccount.objects.select_for_update().get(user=user)

        if account.balance < withdrawal_amount:
            raise ValueError(f"Insufficient balance for user {user}")

        # Deduct the withdrawal amount and save the new balance
        account.balance -= withdrawal_amount
        account.save()

        print(f"Updated user {user}'s balance by subtracting {withdrawal_amount}")
    except USDAccount.DoesNotExist:
        raise ValueError(f"User with ID {user} does not have a USD account")


# Crypto
def process_allbridge_withdrawal(user, recipient_address, withdrawal_amount):
    # Step 1: Convert platform asset to USDC if necessary
    usdc_amount = convert_to_usdc(user, withdrawal_amount)

    # Step 2: Use AllBridge to bridge USDC to the recipient blockchain
    try:
        bridge_response = allbridge_bridge(
            from_chain="Stellar",  # E.g., Stellar
            to_chain=get_target_blockchain(recipient_address),  # E.g., Ethereum, Solana
            amount=usdc_amount,
            recipient=recipient_address
        )

        if bridge_response["status"] == "success":
            return "success"
        else:
            return f"failure: {bridge_response.get('error', 'Unknown error')}"

    except Exception as e:
        return f"failure: {str(e)}"


def allbridge_bridge(from_chain, to_chain, amount, recipient):
    # This function should make the actual API call to AllBridge
    allbridge_api_url = "https://api.allbridge.io/bridge"
    payload = {
        "from_chain": from_chain,
        "to_chain": to_chain,
        "amount": amount,
        "recipient_address": recipient
    }
    response = requests.post(allbridge_api_url, json=payload)
    return response.json()


def convert_to_usdc(user, amount):
    # In case of any conversion, you could integrate it here.
    # Example: Convert USD or other stablecoins to USDC
    return amount  # Assuming no conversion needed for this example


def process_simpleswap_withdrawal(user, recipient_address, withdrawal_amount):
    # Step 1: Convert pooled assets to the requested cryptocurrency using SimpleSwap
    try:
        simpleswap_response = simpleswap_convert(
            from_currency="USDC",
            to_currency=get_currency_by_address(recipient_address),  # E.g., BTC
            amount=withdrawal_amount,
            recipient=recipient_address
        )

        if simpleswap_response["status"] == "success":
            return "success"
        else:
            return f"failure: {simpleswap_response.get('error', 'Unknown error')}"

    except Exception as e:
        return f"failure: {str(e)}"


def simpleswap_convert(from_currency, to_currency, amount, recipient):
    # This function should make the actual API call to SimpleSwap
    simpleswap_api_url = "https://api.simpleswap.io/v1/convert"
    payload = {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "amount": amount,
        "recipient_address": recipient
    }
    response = requests.post(simpleswap_api_url, json=payload)
    return response.json()


def get_currency_by_address(recipient_address):
    # This function returns the correct currency based on the address type
    if is_btc_address(recipient_address):
        return "BTC"
    elif is_ltc_address(recipient_address):
        return "LTC"
    # Add more logic for other currencies (ETH, etc.)
    elif is_eth_address(recipient_address):
        return "ETH"
    elif is_stellar_address(recipient_address):
        return "USDC"
    elif is_solana_address(recipient_address):
        return "SOL"
    else:
        raise ValueError("Unsupported address type")


def supports_usdc(address):
    """
    Checks if the given address belongs to a blockchain that supports USDC, such as Ethereum or Solana.
    """
    return is_eth_address(address) or is_solana_address(address)


def is_btc_address(address):
    # Regex pattern for validating Bitcoin addresses
    btc_pattern = r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"
    return re.match(btc_pattern, address) is not None


def is_ltc_address(address):
    # Regex pattern for validating Litecoin addresses
    ltc_pattern = r"^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$"
    return re.match(ltc_pattern, address) is not None


def is_eth_address(address):
    # Simple check for Ethereum addresses (starts with 0x and has 40 hex characters)
    eth_pattern = r"^0x[a-fA-F0-9]{40}$"
    return re.match(eth_pattern, address) is not None


def is_solana_address(address):
    solana_pattern = r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"
    return re.match(solana_pattern, address) is not None


def is_stellar_address(address):
    """
    Detect if an address is a Stellar public key.
    Stellar public keys always start with 'G' and are 56 characters long.
    """
    return address.startswith('G') and len(address) == 56


def get_target_blockchain(recipient_address):
    # Logic to determine which blockchain to use based on recipient address
    if is_eth_address(recipient_address):
        return "Ethereum"
    elif is_btc_address(recipient_address):
        return "Bitcoin"
    elif is_ltc_address(recipient_address):
        return "Litecoin"
    elif is_solana_address(recipient_address):
        return "Solana"
    elif is_stellar_address(recipient_address):
        return "Stellar"
    else:
        raise ValueError("Unsupported blockchain")


def validate_stellar_address(address):
    try:
        Keypair.from_public_key(address)  # This will raise an exception if the address is invalid
        return True
    except ValueError:
        return False


# Circle



def generate_unique_idempotency_key():
    """Generates a unique idempotency key using UUID."""
    return str(uuid.uuid4())  # UUID for idempotency key


def get_user_linked_account(user, account_number):
    """Fetches the user's linked bank account."""
    try:
        linked_account = LinkedAccount.objects.filter(user=user).first()
        if linked_account:
            return linked_account
        else:
            logger.error(f"No linked account found for user {user}")
            raise ValueError("Linked account not found")
    except Exception as e:
        logger.error(f"Error fetching linked account for user {user}: {str(e)}")
        raise ValueError("Error fetching linked account")


def validate_address(address):
    """
    Validate a cryptocurrency address.

    :param address: The address to validate.
    :return: True if valid, False otherwise.
    """
    # Example regex for Bitcoin address (you can adjust this for different types)
    bitcoin_address_pattern = r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$'  # Simple pattern for Bitcoin
    ethereum_address_pattern = r'^0x[a-fA-F0-9]{40}$'  # Simple pattern for Ethereum

    if re.match(bitcoin_address_pattern, address):
        return True
    elif re.match(ethereum_address_pattern, address):
        return True

    return False


def validate_account_number(account_number):
    """
    Validate a bank account number.

    :param account_number: The account number to validate.
    :return: True if valid, False otherwise.
    """
    # Check if account number is a string of digits, and has a specific length
    if isinstance(account_number, str) and account_number.isdigit() and 8 <= len(
            account_number) <= 12:  # Example: between 8 and 12 digits
        return True

    return False
