import logging
from decimal import Decimal

from app.models import USDAccount, Transaction
from app.services.transact.utils.stellar_network_service import process_stellar_withdrawal, has_trustline
from app.services.transact.transfer import InsufficientFundsError
from app.services.transact.utils.transfer_stellar_USDC_to_circle_wallet import send_stellar_usdc_to_circle, \
    CircleWithdrawalProvider, create_bank_account_recipient, initiate_bank_withdrawal, confirm_bank_transfer
from app.services.transact.utils.crypto import is_stellar_address, supports_usdc, get_user_virtual_balance, \
    process_allbridge_withdrawal

logger = logging.getLogger(__name__)

BASE_URL = "https://api.circle.com/v1"
BANK_ACCOUNT_CREATE_URL = f"{BASE_URL}/banks/wires"


class WithdrawalService:
    def __init__(self, user, amount, method, to_currency=None, recipient_address=None, destination=None):
        self.user = user
        self.amount = Decimal(amount)
        self.method = method
        self.to_currency = to_currency  # For crypto withdrawals
        self.recipient_address = recipient_address  # For crypto withdrawals
        self.destination = destination  # For Circle withdrawals

    def validate_balance(self):
        wallet = self.get_user_wallet()
        if wallet.balance < self.amount:
            raise InsufficientFundsError("Insufficient funds")
        return wallet

    def get_user_wallet(self):
        try:
            return USDAccount.objects.get(user=self.user)
        except USDAccount.DoesNotExist:
            logger.error(f"User {self.user.id} has no USD account.")
            raise ValueError("USD account not found.")

    def create_transaction(self, status="pending"):
        try:
            return Transaction.objects.create(
                user=self.user,
                transaction_type="withdrawal",
                amount=self.amount,
                status=status,
                gateway=self.method
            )
        except Exception as e:
            logger.error(f"Error creating transaction for user {self.user.id}: {str(e)}")
            raise ValueError("Error creating withdrawal transaction.")

    def update_user_balance(self, wallet):
        try:
            wallet.balance -= self.amount
            wallet.save()
            logger.info(f"User {self.user.id} balance updated. New balance: {wallet.balance}")
        except Exception as e:
            logger.error(f"Error updating balance for user {self.user.id}: {str(e)}")
            raise ValueError("Error updating user balance.")

    def call_gateway(self):
        if self.method == 'circle':
            return self.handle_circle_withdrawal(self.amount, self.destination)
        elif self.method == 'yellow':
            return self.handle_yellow_withdrawal()
        elif self.method == 'crypto':
            return self.withdraw_crypto()
        else:
            logger.error(f"Unknown withdrawal method: {self.method}")
            raise ValueError(f"Unknown withdrawal method: {self.method}")

    def process(self):
        try:
            if self.method == 'crypto' and not self.recipient_address:
                logger.error(f"Recipient address is None for user {self.user.id}")
                return {"error": "Recipient address must be provided."}, 400

            wallet = self.validate_balance()
            result = self.call_gateway()

            if result.get("status") == "success":
                self.update_user_balance(wallet)
                self.create_transaction(status="success")
                logger.info(f"Withdrawal successful for user {self.user.id}: {result.get('transaction_id')}")
                return {"message": "Withdrawal initiated successfully."}, 200
            else:
                logger.error(f"Withdrawal failed for user {self.user.id}: {result}")
                return {"error": "Withdrawal failed. Please try again."}, 400

        except Exception as e:
            logger.error(f"Error during withdrawal for user {self.user.id}: {str(e)}")
            return {"error": str(e)}, 400

    # Handle crypto withdrawals
    def withdraw_crypto(self):
        # Get user balance and check if there are sufficient funds
        user_balance = get_user_virtual_balance(self.user)

        if self.amount > user_balance:
            logger.error(
                f"Insufficient virtual balance for user {self.user.id}. Requested: {self.amount}, Available: {user_balance}"
            )
            raise InsufficientFundsError("Insufficient virtual balance")

        # Check if recipient address is provided
        if not self.recipient_address:
            logger.error(f"Recipient address is None for user {self.user.id}")
            raise ValueError("Recipient address must be provided.")

        # Stellar withdrawal process
        if is_stellar_address(self.recipient_address):
            if not has_trustline(self.recipient_address, asset_code="USDC"):
                logger.error(f"Recipient {self.recipient_address} does not have a trustline for USDC")
                return {"error": "Recipient does not have a trustline for USDC."}

            return process_stellar_withdrawal(self.user, self.recipient_address, self.amount)

        # Allbridge USDC withdrawal process
        elif supports_usdc(self.recipient_address):
            return process_allbridge_withdrawal(self.recipient_address, self.amount)

        # Unsupported blockchain
        else:
            logger.error(
                f"Blockchain not supported for user {self.user.id} with recipient address {self.recipient_address}"
            )
            return {"error": "Blockchain Not Supported"}

    # Handle Circle withdrawal
    @staticmethod
    def handle_circle_withdrawal(stellar_amount: str, bank_details: dict):
        """
        Handles the full Circle withdrawal process:
        1. Transfers USDC from Stellar to Circle.
        2. Creates a bank account recipient for withdrawal.
        3. Initiates and confirms the bank withdrawal.

        Args:
            stellar_amount (str): The amount of USDC to be transferred.
            bank_details (dict): Bank account details (name, account number, routing number).

        Returns:
            bool: True if the entire process completes successfully, False otherwise.
        """
        try:
            # Step 1: Transfer USDC from Stellar to Circle
            logger.info(f"Transferring {stellar_amount} USDC from Stellar to Circle...")
            transaction_response = send_stellar_usdc_to_circle(stellar_amount)

            if not transaction_response.get("successful"):
                raise Exception("Failed to transfer USDC to Circle.")

            logger.info("USDC successfully transferred to Circle.")

            # Step 2: Create bank account recipient
            recipient_info = create_bank_account_recipient(bank_details)
            if not recipient_info:
                raise Exception("Failed to create bank account recipient.")

            # Step 3: Initiate bank withdrawal
            logger.info("Initiating bank withdrawal...")
            transaction_id = initiate_bank_withdrawal(stellar_amount, recipient_info["id"])
            if not transaction_id:
                raise Exception("Failed to initiate bank withdrawal.")

            # Step 4: Confirm bank transfer
            logger.info("Confirming the bank transfer...")
            status = confirm_bank_transfer(transaction_id)
            if status == "confirmed":
                logger.info("Withdrawal confirmed, funds have been transferred to the bank.")
                return True
            else:
                logger.warning(f"Transfer status: {status}")
                return False

        except Exception as e:
            logger.error(f"Error during Circle withdrawal process: {e}")
            return False

