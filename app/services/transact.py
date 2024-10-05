import logging

import transaction
from django.db import transaction
from app.models import USDAccount, Transaction
from app.services.stellar_anchor_service import StellarAnchorService
from app.services.utils import calculate_fee, has_sufficient_balance

logger = logging.getLogger(__name__)


class InsufficientFundsError(Exception):
    pass


class UserNotVerifiedError(Exception):
    pass


class DepositService:
    def __init__(self):
        self.anchor_service = StellarAnchorService()

    def initiate_deposit(self, user, amount):
        # Step 1: Calculate fees using the Fee model
        total_amount, fee_amount, net_amount = calculate_fee('deposit', amount)

        # Step 2: Initiate deposit with anchor
        anchor_response = self.anchor_service.initiate_deposit(user, net_amount)

        if 'error' in anchor_response:
            return anchor_response

        # Step 3: Create pending transaction record
        txn = Transaction.objects.create(
            user=user,
            amount=amount,
            fee=fee_amount,  # Record the fee
            transaction_type='deposit',
            status='pending',
            external_transaction_id=anchor_response.get('id')
        )

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
                    usd_account = USDAccount.objects.select_for_update().get(user=transaction.user)
                    usd_account.deposit(transaction.amount)

                    transaction.status = 'completed'
                    transaction.save()
                    logger.info(f"Deposit completed for transaction {transaction.id}")

                elif callback_data['status'] == 'failed':
                    transaction.status = 'failed'
                    transaction.save()
                    logger.warning(f"Deposit failed for transaction {transaction.id}")

        except Transaction.DoesNotExist:
            logger.error(f"Transaction not found for id {callback_data['transaction_id']}")
            return {'error': 'Transaction not found'}
        except Exception as e:
            logger.error(f"Error processing deposit callback: {e}")
            raise


class WithdrawalService:
    def __init__(self):
        self.anchor_service = StellarAnchorService()

    def initiate_withdrawal(self, user, amount):
        if not user.is_verified():
            return {'error': 'User not KYC verified'}

        # Step 1: Calculate fees using the Fee model
        total_amount, fee_amount, net_amount = calculate_fee('withdrawal', amount)

        try:
            usd_account = USDAccount.objects.select_for_update().get(user=user)

            if not has_sufficient_balance(usd_account, total_amount):
                return {'error': 'Insufficient funds'}

            with transaction.atomic():
                # Step 2: Initiate withdrawal with anchor
                anchor_response = self.anchor_service.initiate_withdrawal(user, net_amount)
                if 'error' in anchor_response:
                    return anchor_response

                # Step 3: Create pending transaction record and deduct balance
                txn = Transaction.objects.create(
                    user=user,
                    amount=amount,
                    fee=fee_amount,  # Record the fee
                    transaction_type='withdrawal',
                    status='pending',
                    external_transaction_id=anchor_response.get('id')
                )
                usd_account.withdraw(total_amount)

            logger.info(f"Withdrawal initiated for user {user.id}, transaction {transaction.id}")
            return {
                'status': 'initiated',
                'transaction_id': transaction.id,
                'more_info_url': anchor_response.get('url')  # URL where user completes the withdrawal
            }

        except USDAccount.DoesNotExist:
            logger.error(f"User {user.id} USD account not found")
            return {'error': 'User USD account not found'}
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
                    transaction.status = 'completed'
                    transaction.save()
                    logger.info(f"Withdrawal completed for transaction {transaction.id}")

                elif callback_data['status'] == 'failed':
                    usd_account = USDAccount.objects.select_for_update().get(user=transaction.user)
                    usd_account.deposit(transaction.amount)  # Refund
                    transaction.status = 'failed'
                    transaction.save()

                    logger.error(f"Withdrawal failed for transaction {callback_data['transaction_id']}")

        except Transaction.DoesNotExist:
            logger.error(f"Transaction not found for id {callback_data['transaction_id']}")
            return {'error': 'Transaction not found'}
        except Exception as e:
            logger.error(f"Error processing withdrawal callback: {e}")
            raise


class TransferService:
    def process_internal_transfer(self, sender, recipient, amount):
        if not sender.is_verified():
            return {'error': 'User not KYC verified'}

        # Step 1: Calculate fees using the Fee model
        total_amount, fee_amount, net_amount = calculate_fee('transfer', amount)

        try:
            with transaction.atomic():
                sender_account = USDAccount.objects.select_for_update().get(user=sender)
                recipient_account = USDAccount.objects.select_for_update().get(user=recipient)

                if not has_sufficient_balance(sender_account, total_amount):
                    raise InsufficientFundsError("Insufficient funds")

                # Step 2: Proceed with the transfer
                sender_account.withdraw(total_amount)
                recipient_account.deposit(net_amount)

                # Step 3: Create transaction records
                self._create_transaction(sender, 'transfer', total_amount, f"Transfer to {recipient.username}")
                self._create_transaction(recipient, 'transfer', net_amount, f"Transfer from {sender.username}")

            logger.info(f"Transfer successful from {sender.username} to {recipient.username}")
            return {'status': 'success'}

        except InsufficientFundsError as e:
            logger.error(f"Insufficient funds for {sender.username}: {e}")
            return {'error': 'Insufficient funds'}
        except Exception as e:
            logger.error(f"Error during transfer: {e}")
            raise

    @staticmethod
    def _create_transaction(user, transaction_type, amount, description):
        Transaction.objects.create(
            user=user,
            amount=amount,
            transaction_type=transaction_type,
            status='completed',
            description=description
        )
