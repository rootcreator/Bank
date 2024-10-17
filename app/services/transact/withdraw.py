import logging
from decimal import Decimal

from app.models import USDAccount, Transaction

logger = logging.getLogger(__name__)


class WithdrawalService:
    def __init__(self, user, amount, method):
        self.user = user
        self.amount = Decimal(amount)
        self.method = method  # e.g., 'circle', 'wyre', 'bank_transfer', 'crypto'

    def validate_balance(self):
        # Ensure that the user has sufficient funds for withdrawal
        wallet = USDAccount.objects.get(user=self.user)
        if wallet.balance < self.amount:
            raise ValueError('Insufficient funds')
        return wallet

    def create_transaction(self):
        # Create a withdrawal transaction with pending status
        return Transaction.objects.create(
            user=self.user,
            transaction_type="withdrawal",
            amount=self.amount,
            status="pending",
            gateway=self.method  # Track the method of withdrawal
        )

    def update_user_balance(self, wallet):
        """
        Update the user's virtual balance after a successful withdrawal.
        This function deducts the withdrawal amount from the user's balance.
        """
        wallet.balance -= self.amount  # Deduct the amount from the user's balance
        wallet.save()  # Save the updated balance to the database
        logger.info(f"User {self.user.id} balance updated. New balance: {wallet.balance}")

    def call_gateway(self):
        # Dynamically call the appropriate withdrawal method based on `self.method`
        if self.method == 'circle':
            result = self.handle_circle_withdrawal()
        elif self.method == 'wyre':
            result = self.handle_wyre_withdrawal()
        elif self.method == 'bank_transfer':
            result = self.handle_bank_transfer_withdrawal()
        elif self.method == 'crypto':
            result = self.handle_crypto_withdrawal()
        else:
            raise ValueError(f"Unknown withdrawal method: {self.method}")

        return result

    def handle_circle_withdrawal(self):
        # Placeholder: Call Circle API for withdrawal
        return {"transaction_id": "circle_withdrawal_789", "status": "success"}

    def handle_wyre_withdrawal(self):
        # Placeholder: Call Wyre API for withdrawal
        return {"transaction_id": "wyre_withdrawal_456", "status": "success"}

    def handle_bank_transfer_withdrawal(self):
        # Placeholder: Bank transfer logic
        return {"transaction_id": "bank_transfer_123", "status": "success"}

    def handle_crypto_withdrawal(self):
        # Placeholder: Crypto withdrawal logic
        return {"transaction_id": "crypto_withdrawal_321", "status": "success"}

    def process(self):
        """
        Main method to process the withdrawal:
        1. Validate the user's balance.
        2. Call the appropriate withdrawal method.
        3. Deduct balance and save the transaction if successful.
        """
        try:
            # Validate the balance before initiating the withdrawal
            wallet = self.validate_balance()

            # Call the selected gateway to initiate the withdrawal
            result = self.call_gateway()

            if result.get("status") == "success":
                # Update the user's virtual balance after successful withdrawal
                self.update_user_balance(wallet)

                # Create a transaction record in the database
                self.create_transaction()

                logger.info(f"Withdrawal successful for user {self.user.id}: {result['transaction_id']}")
                return {"message": "Withdrawal initiated successfully. Funds will be transferred soon."}, 200
            else:
                # Log failure and return an error response
                logger.error(f"Withdrawal failed for user {self.user.id}: {result}")
                return {"error": "Withdrawal failed. Please try again later."}, 400

        except Exception as e:
            # Handle any exceptions that occur during the withdrawal process
            logger.error(f"Error during withdrawal for user {self.user.id}: {str(e)}")
            return {"error": str(e)}, 400
