import logging
import uuid

import transaction
from django.db import transaction

from app.models import USDAccount, Transaction, PlatformAccount
from app.services.utils import calculate_fee, has_sufficient_balance

logger = logging.getLogger(__name__)


class InsufficientFundsError(Exception):
    pass


class UserNotVerifiedError(Exception):
    pass


class TransferService:
    def process_internal_transfer(self, sender, recipient, amount):
        """if not sender.is_kyc_completed():
            raise ValueError('User not KYC verified')"""

        if amount <= 0:
            raise ValueError('Transfer amount must be greater than zero')

        # Step 1: Calculate fees using the Fee model
        total_amount, fee_amount, net_amount = calculate_fee('transfer', amount)

        # Generate a unique transaction ID for this transfer
        internal_transaction_id = {'id': str(uuid.uuid4())}

        try:
            with transaction.atomic():
                sender_account = USDAccount.objects.select_for_update().get(user=sender)
                recipient_account = USDAccount.objects.select_for_update().get(user=recipient)

                if not has_sufficient_balance(sender_account, total_amount):
                    raise InsufficientFundsError("Insufficient funds")

                # Step 2: Proceed with the transfer
                sender_account.withdraw(total_amount)
                recipient_account.deposit(net_amount)

                # Step 3: Fetch the platform account for commissions
                platform_account = PlatformAccount.objects.get(name='Commission')
                platform_account.deposit(fee_amount)

                # Step 4: Create transaction records for both sender, recipient, and the fee
                self._create_transaction(sender, 'transfer', total_amount, f"Transfer to {recipient.username}",
                                         internal_transaction_id)
                self._create_transaction(recipient, 'transfer', net_amount, f"Transfer from {sender.username}",
                                         internal_transaction_id)
                self._create_transaction(sender, 'fee', fee_amount, "Transfer fee", internal_transaction_id)

            logger.info(f"Transfer successful from {sender.username} to {recipient.username}")
            return {'status': 'success'}

        except InsufficientFundsError as e:
            logger.error(f"Insufficient funds for {sender.username}: {e}")
            raise

        except Exception as e:
            logger.error(f"Error during transfer: {e}")
            raise

    @staticmethod
    def _create_transaction(user, transaction_type, amount, description, internal_transaction_id):
        # Create transaction entry with internal transaction ID
        Transaction.objects.create(
            user=user,
            amount=amount,
            transaction_type=transaction_type,
            status='completed',
            description=description,
            internal_transaction_id=internal_transaction_id.get('id')  # Use the same ID for both transactions
        )
