import logging
from decimal import Decimal

from stellar_sdk import transaction

from app.models import USDAccount, Transaction
from app.services.stellar_network_service import process_stellar_withdrawal, process_stellar_to_circle_withdrawal
from app.services.transact.circle import CircleAPI, get_user_bank_account_id
from app.services.transact.transfer import InsufficientFundsError
from app.services.transact.withdrawal_utils import (process_allbridge_withdrawal,
                                                    process_simpleswap_withdrawal, get_user_virtual_balance,
                                                    is_stellar_address,
                                                    supports_usdc, update_user_virtual_balance
                                                    )

logger = logging.getLogger(__name__)


class WithdrawalService:
    def __init__(self, user, amount, method, to_currency=None, recipient_address=None, destination=None):
        """
        Handles withdrawal requests from USD to other currencies or methods.

        :param user: The user requesting the withdrawal.
        :param amount: The amount of USD to withdraw.
        :param method: The method of withdrawal ('circle', 'yellow', 'crypto').
        :param to_currency: The target cryptocurrency for crypto withdrawals (optional).
        :param recipient_address: The address to send the converted cryptocurrency (optional).
        :param destination: The withdrawal destination for Circle method (optional).
        """
        self.user = user
        self.amount = Decimal(amount)
        self.method = method
        self.to_currency = to_currency  # For crypto withdrawals
        self.recipient_address = recipient_address  # For crypto withdrawals
        self.destination = destination  # For Circle withdrawals

    def validate_balance(self):
        """Ensures that the user has sufficient funds for withdrawal."""
        wallet = self.get_user_wallet()
        if wallet.balance < self.amount:
            raise InsufficientFundsError("Insufficient funds")
        return wallet

    def get_user_wallet(self):
        """Fetches the user's wallet, handling exceptions."""
        try:
            return USDAccount.objects.get(user=self.user)
        except USDAccount.DoesNotExist:
            logger.error(f"User {self.user.id} has no USD account.")
            raise ValueError("USD account not found.")

    def create_transaction(self, status="pending"):
        """Creates a withdrawal transaction with the specified status."""
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
        """Updates the user's balance after a successful withdrawal."""
        try:
            wallet.balance -= self.amount
            wallet.save()
            logger.info(f"User {self.user.id} balance updated. New balance: {wallet.balance}")
        except Exception as e:
            logger.error(f"Error updating balance for user {self.user.id}: {str(e)}")
            raise ValueError("Error updating user balance.")

    def call_gateway(self):
        """Calls the appropriate withdrawal method based on `self.method`."""
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
        """Main method to process the withdrawal."""
        try:
            # Validate that a recipient address is provided for crypto withdrawals
            if self.method == 'crypto' and not self.recipient_address:
                logger.error(f"Recipient address is None for user {self.user.id}")
                return {"error": "Recipient address must be provided."}, 400

            wallet = self.validate_balance()  # Step 1: Validate user balance
            result = self.call_gateway()  # Step 2: Call the appropriate gateway

            if result.get("status") == "success":
                self.update_user_balance(wallet)  # Step 3: Update user balance
                self.create_transaction(status="success")  # Step 4: Log transaction

                logger.info(f"Withdrawal successful for user {self.user.id}: {result.get('transaction_id')}")
                return {"message": "Withdrawal initiated successfully."}, 200
            else:
                logger.error(f"Withdrawal failed for user {self.user.id}: {result}")
                return {"error": "Withdrawal failed. Please try again."}, 400

        except Exception as e:
            logger.error(f"Error during withdrawal for user {self.user.id}: {str(e)}")
            return {"error": str(e)}, 400

    # --- Crypto Withdrawal Logic ---
    def withdraw_crypto(self):
        """Handles cryptocurrency withdrawals."""
        user_balance = get_user_virtual_balance(self.user)  # Check user's virtual balance
        if self.amount > user_balance:
            raise InsufficientFundsError("Insufficient virtual balance")

        # Check if recipient_address is None
        if not self.recipient_address:
            logger.error(f"Recipient address is None for user {self.user.id}")
            raise ValueError("Recipient address must be provided.")

        if is_stellar_address(self.recipient_address):
            return self._process_stellar_withdrawal()
        elif supports_usdc(self.recipient_address):
            return self._process_allbridge_withdrawal()
        else:
            return self._process_simpleswap_withdrawal()

    def _process_stellar_withdrawal(self):
        """Processes Stellar network withdrawals."""
        try:
            transaction_status = process_stellar_withdrawal(self.user, self.recipient_address, self.amount)
            return self._handle_withdrawal_result(transaction_status)
        except Exception as e:
            logger.error(f"Error in Stellar withdrawal: {str(e)}")
            return {"error": f"Stellar withdrawal failed: {str(e)}"}

    def _process_allbridge_withdrawal(self):
        """Processes AllBridge network withdrawals for USDC-supported blockchains."""
        try:
            transaction_status = process_allbridge_withdrawal(self.user, self.recipient_address, self.amount)
            return self._handle_withdrawal_result(transaction_status)
        except Exception as e:
            logger.error(f"Error in AllBridge withdrawal: {str(e)}")
            return {"error": f"AllBridge withdrawal failed: {str(e)}"}

    def _process_simpleswap_withdrawal(self):
        """Processes withdrawals using SimpleSwap for non-USDC cryptocurrencies."""
        try:
            transaction_status = process_simpleswap_withdrawal(self.user, self.recipient_address, self.amount)
            return self._handle_withdrawal_result(transaction_status)
        except Exception as e:
            logger.error(f"Error in SimpleSwap withdrawal: {str(e)}")
            return {"error": f"SimpleSwap withdrawal failed: {str(e)}"}

    def _handle_withdrawal_result(self, transaction_status):
        """Handles the result of a withdrawal operation."""
        if transaction_status == "success":
            try:
                with transaction.atomic():  # Atomic transaction to ensure data integrity
                    update_user_virtual_balance(self.user.id, self.amount)  # Deduct virtual balance
                return {"status": "success", "message": "Withdrawal successful"}
            except Exception as e:
                logger.error(f"Error updating virtual balance: {str(e)}")
                return {"error": f"Withdrawal failed: {str(e)}"}
        else:
            return {"error": "Withdrawal failed"}

    # --- Circle Withdrawal Logic ---
    def handle_circle_withdrawal(self,withdrawal_amount, account_numer):
        """Handles Circle withdrawal logic."""
        try:
            # Step 1: Validate user balance
            user_balance = get_user_virtual_balance(self.user)
            if user_balance < self.amount:
                logger.error(
                    f"Insufficient funds for user {self.user.id}. Available: {user_balance}, Required: {self.amount}")
                return {"error": "Insufficient funds."}

            # Step 2: Withdraw from Stellar (Assuming this is handled by your existing logic)
            stellar_withdrawal_response = process_stellar_to_circle_withdrawal(self.user, self.amount)

            if stellar_withdrawal_response != "success":
                logger.error(f"Withdrawal from Stellar failed for user {self.user.id}: {stellar_withdrawal_response}")
                return {"error": "Withdrawal from Stellar failed."}

            # Step 3: Prepare payout data for Circle
            payout_data = {
                "amount": str(self.amount),  # Convert amount to string
                "currency": "USD",
                "recipient": {
                    "bank_account_id": get_user_bank_account_id(self.user),  # Fetch the bank account ID
                    "type": "ACH"  # or "wire" depending on the type of transfer
                },
                "description": "Withdrawal to bank account"
            }

            # Step 4: Create Circle payout
            circle_response = CircleAPI.create_payout(payout_data)
            if "error" in circle_response:
                logger.error(f"Circle payout creation failed for user {self.user.id}: {circle_response['error']}")
                return {"error": "Circle payout creation failed."}

            logger.info(f"Circle withdrawal successful for user {self.user.id}: {circle_response}")
            return {"status": "success", "message": "Withdrawal initiated successfully.",
                    "transaction_id": circle_response.get("id")}

        except Exception as e:
            logger.error(f"Error during Circle withdrawal for user {self.user.id}: {str(e)}")
            return {"error": str(e)}

    # --- Yellow Withdrawal Logic ---
    def handle_yellow_withdrawal(self):
        """Handles Yellow withdrawal logic."""
        try:
            # Placeholder for Yellow integration
            logger.info(f"Yellow withdrawal initiated for user {self.user.id}")
            return {"status": "success", "message": "Yellow withdrawal successful"}
        except Exception as e:
            logger.error(f"Error during Yellow withdrawal for user {self.user.id}: {str(e)}")
            return {"error": f"Yellow withdrawal failed: {str(e)}"}
