import logging

from stellar_sdk import Server, Keypair, TransactionBuilder, Network, server

from app.services.transact.utils.transfer_stellar_USDC_to_circle_wallet import STELLAR_SERVER, STELLAR_SECRET_KEY, \
    STELLAR_PUBLIC_KEY, USDC_ASSET

# Logger setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Constants for the accounts
CIRCLE_LIQUIDITY_ACCOUNT = "GAYF33NNNMI2Z6VNRFXQ64D4E4SF77PM46NW3ZUZEEU5X7FCHAZCMHKU"  # Circle's account
USDC_ISSUER = "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5"  # USDC issuer account


def establish_trustline_for_usdc():
    try:
        account = STELLAR_SERVER.load_account(STELLAR_PUBLIC_KEY)
        keypair = Keypair.from_secret(STELLAR_SECRET_KEY)

        transaction_builder = TransactionBuilder(
            source_account=account,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            base_fee=STELLAR_SERVER.fetch_base_fee()
        )
        # Add Change Trust Operation
        transaction = transaction_builder.append_change_trust_op(
            asset=USDC_ASSET
        ).set_timeout(30).build()

        # Sign and Submit
        transaction.sign(keypair)
        response = STELLAR_SERVER.submit_transaction(transaction)
        print(f"Trustline established: {response}")
        return response
    except Exception as e:
        print(f"Error establishing trustline for USDC: {e}")
        return None


def has_trustline(recipient_address, asset_code="USDC"):
    # Check if recipient has trustline for the asset
    try:
        account = server.accounts().account_id(recipient_address).call()
        balances = account['balances']
        for balance in balances:
            if balance.get('asset_code') == asset_code:
                return True
        return False
    except Exception as e:
        return False  # Could handle more specific exceptions here


def process_stellar_withdrawal(user, recipient_address, withdrawal_amount):
    # Ensure trustline is set up before proceeding
    if not establish_trustline_for_usdc():
        raise Exception("Failed to establish trustline for USDC.")

    # Set up Stellar server and keys
    server = Server("https://horizon-testnet.stellar.org")
    platform_keypair = Keypair.from_secret("SC34UKYKGMAUFWRZNB7ELZDKHJILDMR4SYSKD3B2MEM5YDMGF7US2M3L")
    platform_public_key = platform_keypair.public_key

    # Load account from Stellar network
    platform_account = server.load_account(account_id=platform_public_key)

    # Create a Stellar transaction
    transaction = TransactionBuilder(
        source_account=platform_account,
        network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
        base_fee=100
    ).add_text_memo("Withdrawal").append_payment_op(
        destination=recipient_address,
        asset="USDC",  # or "USD" for USD-backed tokens
        amount=str(withdrawal_amount)
    ).build()

    # Sign the transaction
    transaction.sign(platform_keypair)

    # Submit the transaction to the Stellar network
    try:
        response = server.submit_transaction(transaction)
        if response['successful']:
            return "success"
        else:
            result_codes = response.get('extras', {}).get('result_codes', {})
            if result_codes.get('operations', [])[0] == 'op_no_trust':
                return {
                    "error": "The recipient address does not have a "
                             "trustline for the asset you're trying to send. "
                             "Please inform the recipient to set up a trustline for USDC."
                }
            else:
                return f"failure: {response.get('extras', {}).get('result_codes', {})}"
    except Exception as e:
        return f"failure: {str(e)}"
