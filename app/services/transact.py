import logging
import uuid

import transaction
from django.db import transaction
from validators import ValidationError

from app.models import USDAccount, Transaction, PlatformAccount
from app.services.paymentgateway import PaymentGateway, CircleGateway
from app.services.reconciliation import ReconciliationService
from app.services.stellar_anchor_service import StellarAnchorService
from app.services.utils import calculate_fee, has_sufficient_balance

logger = logging.getLogger(__name__)


class InsufficientFundsError(Exception):
    pass


class UserNotVerifiedError(Exception):
    pass


def convert_fiat_to_stellar(amount):
    pass


class DepositService:
    def __init__(self):
        # Initialize the StellarAnchorService with a list of concrete gateway instances
        gateways = [CircleGateway()]  # Add more gateways if needed
        self.anchor_service = StellarAnchorService(gateways)

    def initiate_deposit(self, user, amount):

        if amount <= 0:
            return {"error": "Deposit amount must greater than zero"}

        # Step 1: Calculate fees using the Fee model
        total_amount, fee_amount, net_amount = calculate_fee('deposit', amount)

        # Step 2: Initiate deposit with anchor
        anchor_response = self.anchor_service.initiate_deposit(user, net_amount)

        if 'error' in anchor_response:
            return anchor_response

        # Step 2: Convert fiat to Stellar (optional)
        stellar_amount = convert_fiat_to_stellar(amount)  # Implement conversion logic


        # Step 3: Create pending transaction record
        txn = Transaction.objects.create(
            user=user,
            amount=amount,
            fee=fee_amount,  # Record the fee
            transaction_type='deposit',
            status='pending',
            external_transaction_id=anchor_response.get('id')
        )

        ReconciliationService(stellar_amount)

        # Step 5: Update platform account
        platform_account = PlatformAccount.objects.first()  # Assuming one platform account

        platform_account.balance += net_amount

        platform_account.save()

        usd_account = USDAccount.objects.get(user=user)

        usd_account.deposit(amount)  # Update virtual balance

        return {
            'status': 'initiated',
            'transaction_id': txn.id,
            'more_info_url': anchor_response.get('url')  # URL where user completes the deposit
        }

    @staticmethod
    def process_deposit_callback(callback_data):
        try:
            with transaction.atomic():
                txn = Transaction.objects.select_for_update().get(
                    external_transaction_id=callback_data['transaction_id']
                )

                if callback_data['status'] == 'completed':
                    usd_account = USDAccount.objects.select_for_update().get(user=txn.user)
                    usd_account.deposit(txn.amount)

                    txn.status = 'completed'
                    txn.save()
                    logger.info(f"Deposit completed for transaction {txn.id}")

                elif callback_data['status'] == 'failed':
                    txn.status = 'failed'
                    txn.save()
                    logger.warning(f"Deposit failed for transaction {txn.id}")

        except Transaction.DoesNotExist:
            logger.error(f"Transaction not found for id {callback_data['transaction_id']}")
            return {'error': 'Transaction not found'}
        except Exception as e:
            logger.error(f"Error processing deposit callback: {e}")
            raise


class WithdrawalService:
    def __init__(self):
        gateways = [CircleGateway()]  # Add more gateways if needed
        self.anchor_service = StellarAnchorService(gateways)

    @staticmethod
    def has_sufficient_balance(usd_account, amount):
        return usd_account.balance >= amount

    def initiate_withdrawal(self, user, amount):
        # Step 1: Calculate fees using the Fee model
        total_amount, fee_amount, net_amount = calculate_fee('withdrawal', amount)

        try:
            # Get the user's USDAccount (ledger entry)
            usd_account = USDAccount.objects.select_for_update().get(user=user)

            usd_account.withdraw(amount)  # Deduct from user's virtual balance

            platform_account = PlatformAccount.objects.first()  # Assuming one platform account

            platform_account.withdraw(amount)  # Update pooled funds

            # Log the USDAccount for debugging
            logger.debug(f"USDAccount: {usd_account}, Balance: {usd_account.balance}")

            if not self.has_sufficient_balance(usd_account, total_amount):
                return {'error': 'Insufficient funds in ledger'}

            with transaction.atomic():
                # Step 2: Initiate withdrawal with anchor (from pooled account)
                anchor_response = self.anchor_service.initiate_withdrawal(user, net_amount)
                if 'error' in anchor_response:
                    return anchor_response

                # Step 3: Convert fiat to Stellar (if necessary for accounting)
                stellar_amount = convert_fiat_to_stellar(amount)  # Implement conversion logic if needed

                # Step 3: Update platform custody account (optional step, if you track custody balance)
                ReconciliationService(stellar_amount)

                # Step 4: Create pending transaction record and update ledger
                txn = Transaction.objects.create(
                    user=user,
                    amount=amount,
                    fee=fee_amount,
                    transaction_type='withdrawal',
                    status='pending',
                    external_transaction_id=anchor_response.get('id')
                )
                usd_account.withdraw(total_amount)  # Use withdraw method

            logger.info(f"Withdrawal initiated for user {user.id}, transaction {txn.id}")
            return {
                'status': 'initiated',
                'transaction_id': txn.id,
                'more_info_url': anchor_response.get('url')
            }

        except USDAccount.DoesNotExist:
            logger.error(f"User {user.id} USD account ledger not found")
            return {'error': 'User USD account ledger not found'}
        except ValidationError as e:
            logger.error(f"Validation error during withdrawal for user {user.id}: {str(e)}")
            return {'error': str(e)}
        except Exception as e:
            logger.error(f"Error during withdrawal initiation: {e}")
            return {'error': 'Internal error'}

    @staticmethod
    def process_withdrawal_callback(callback_data):
        try:
            with transaction.atomic():
                txn = Transaction.objects.select_for_update().get(
                    external_transaction_id=callback_data['transaction_id']
                )

                if callback_data['status'] == 'completed':
                    txn.status = 'completed'
                    txn.save()
                    logger.info(f"Withdrawal completed for transaction {txn.id}")

                elif callback_data['status'] == 'failed':
                    usd_account = USDAccount.objects.select_for_update().get(user=txn.user)
                    usd_account.deposit(txn.amount + txn.fee)  # Refund to ledger
                    txn.status = 'failed'
                    txn.save()

                    logger.error(f"Withdrawal failed for transaction {callback_data['transaction_id']}")

        except Transaction.DoesNotExist:
            logger.error(f"Transaction not found for id {callback_data['transaction_id']}")
            return {'error': 'Transaction not found'}
        except ValidationError as e:
            logger.error(f"Validation error during withdrawal callback: {str(e)}")
            return {'error': str(e)}
        except Exception as e:
            logger.error(f"Error processing withdrawal callback: {e}")
            raise


class TransferService:
    def process_internal_transfer(self, sender, recipient, amount):
        #if not sender.is_kyc_completed():
        #raise ValueError('User not KYC verified')

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

                # Step 3: Create transaction records for both sender and recipient
                self._create_transaction(sender, 'transfer', total_amount, f"Transfer to {recipient.username}",
                                         internal_transaction_id)
                self._create_transaction(recipient, 'transfer', net_amount, f"Transfer from {sender.username}",
                                         internal_transaction_id)

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
