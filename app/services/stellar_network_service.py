from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset, Payment
from stellar_sdk.exceptions import NotFoundError
import logging

from app.services.transact.withdrawal_utils import get_user_virtual_balance

# Logger setup
logger = logging.getLogger(__name__)


class StellarNetworkService:
    def __init__(self, amount, destination_address, secret_key):
        self.amount = amount
        self.destination_address = destination_address
        self.secret_key = secret_key
        self.horizon_url = "https://horizon.stellar.org"  # Public Stellar network
        self.server = Server(horizon_url=self.horizon_url)

    def perform_transfer(self):
        """Perform the transfer of USDC from the Stellar wallet."""
        try:
            # Load account
            keypair = Keypair.from_secret(self.secret_key)
            source_account = self.server.load_account(keypair.public_key)

            # Create the USDC asset
            usdc_asset = Asset("USDC", "GDU6...")  # Replace with the USDC asset code and issuer

            # Build the transaction
            transaction = (
                TransactionBuilder(
                    source_account=source_account,
                    network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                    base_fee=self.server.fetch_base_fee(),
                )
                .add_operation(
                    operation=Payment(
                        destination=self.destination_address,
                        asset=usdc_asset,
                        amount=str(self.amount),  # Amount must be a string
                    )
                )
                .set_timeout(30)  # Set a timeout for the transaction
                .build()
            )

            # Sign the transaction
            transaction.sign(keypair)

            # Submit the transaction to the Stellar network
            response = self.server.submit_transaction(transaction)

            logger.info(
                f"Transfer successful: {self.amount} USDC to {self.destination_address}. Transaction ID: {response['id']}")
            return {
                "status": "success",
                "transaction_id": response['id']
            }

        except NotFoundError:
            logger.error("Account not found.")
            return {
                "status": "failure",
                "error": "Account not found."
            }
        except Exception as e:
            logger.error(f"Transfer failed: {str(e)}")
            return {
                "status": "failure",
                "error": str(e)
            }


def process_stellar_withdrawal(user, recipient_address, withdrawal_amount):
    # Set up Stellar server and keys
    server = Server("https://horizon-testnet.stellar.org")
    platform_keypair = Keypair.from_secret("SCECAQJKZUNRRBILAFKF5ZPCQZK3M2BIZLUNNMFEJM2KLZ334WRU4ZTC")
    platform_public_key = platform_keypair.public_key

    # Load account from Stellar network
    platform_account = server.load_account(account_id=platform_public_key)

    # Create a Stellar transaction
    transaction = TransactionBuilder(
        source_account=platform_account,
        network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
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
            return f"failure: {response.get('extras', {}).get('result_codes', {})}"
    except Exception as e:
        return f"failure: {str(e)}"


def process_stellar_to_circle_withdrawal(user, withdrawal_amount):
    """Withdraws funds from Stellar and sends to Circle wallet via Circle API."""

    # Set up Stellar server and keys
    server = Server("https://horizon-testnet.stellar.org")
    platform_keypair = Keypair.from_secret("SCECAQJKZUNRRBILAFKF5ZPCQZK3M2BIZLUNNMFEJM2KLZ334WRU4ZTC")
    platform_public_key = platform_keypair.public_key

    # Load account from Stellar network
    platform_account = server.load_account(account_id=platform_public_key)

    # Check if the user has sufficient balance
    user_balance = get_user_virtual_balance(user)  # Implement this function to get user's balance
    if user_balance < withdrawal_amount:
        raise ValueError("Insufficient funds in Stellar account.")

    # Create a Stellar transaction to send USDC to Circle's wallet
    transaction = TransactionBuilder(
        source_account=platform_account,
        network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
        base_fee=100
    ).add_text_memo("Withdrawal to Circle").append_payment_op(
        destination="GAYF33NNNMI2Z6VNRFXQ64D4E4SF77PM46NW3ZUZEEU5X7FCHAZCMHKU",  # Replace with Circle wallet address
        memo="9042254620413856359",
        asset="USDC",
        amount=str(withdrawal_amount)
    ).build()

    # Sign the transaction
    transaction.sign(platform_keypair)

    # Submit the transaction to the Stellar network
    try:
        response = server.submit_transaction(transaction)
        if response['successful']:
            # If successful, you can proceed to handle Circle API logic here
            return "success"
        else:
            return f"failure: {response.get('extras', {}).get('result_codes', {})}"
    except Exception as e:
        return f"failure: {str(e)}"
