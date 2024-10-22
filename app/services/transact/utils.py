import logging
from decimal import Decimal

from app.models import Fee, TRANSACTION_TYPES, Transaction

logger = logging.getLogger(__name__)


def calculate_fee(transaction_type, amount):
    total_amount, fee_amount = Fee.apply_transaction_fee(transaction_type, amount)
    net_amount = Decimal(amount) - fee_amount
    return total_amount, fee_amount, net_amount


def has_sufficient_balance(account, amount):
    return account.balance >= amount


class TransactionService:

    @staticmethod
    def process_transaction(user, transaction_type, amount, description=None):
        # Check for valid transaction type
        if transaction_type not in dict(TRANSACTION_TYPES):
            raise ValueError("Invalid transaction type.")

        # Retrieve user's USD account
        account = user.usd_account

        # Apply transaction fees
        total_amount, fee_amount = Fee.apply_transaction_fee(transaction_type, amount)

        # Perform the transaction (e.g., deposit or withdrawal)
        if transaction_type == 'deposit':
            account.deposit(total_amount)
        elif transaction_type == 'withdrawal':
            account.withdraw(total_amount)
        elif transaction_type == 'transfer':
            # Add your transfer logic here (between users)
            pass

        # Record the transaction in the history
        txn = Transaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            fee_amount=fee_amount,
            status='pending',  # Set status and handle it through business logic
            description=description
        )

        # Set transaction status to completed if all steps succeed
        txn.status = 'completed'
        txn.save()

        return txn


STATE_CODE_MAPPING = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY"
}


def get_state_code(state_name):
    return STATE_CODE_MAPPING.get(state_name, "")  # Return empty if not found





