from polaris.sep24.transaction import create_transaction, get_transaction
from app.models import Transaction, USDAccount
from kyc.models import KYCRequest
from django.conf import settings
from django.shortcuts import get_object_or_404
from decimal import Decimal

class StellarAnchorService:
    def initiate_deposit(self, user, amount):
        # Check KYC status
        kyc_request = get_object_or_404(KYCRequest, user=user.userprofile)
        if kyc_request.status != 'approved':
            return {'error': 'KYC verification is not approved.'}

        try:
            # Create deposit transaction through Polaris
            transaction = create_transaction(
                asset_code="USDC",
                account=settings.STELLAR_PLATFORM_PUBLIC_KEY,  # Use the single custody account
                amount=str(amount),
                kind="deposit"
            )

            # Record the transaction in your system's ledger
            Transaction.objects.create(
                user=user,
                amount=amount,
                transaction_type='deposit',
                status='pending',
                external_transaction_id=transaction.id  # Polaris transaction ID
            )

            return {
                'status': 'initiated',
                'transaction_id': transaction.id,
                'more_info_url': transaction.more_info_url  # URL to Polaris interactive flow
            }

        except Exception as e:
            return {'error': str(e)}

    def initiate_withdrawal(self, user, amount):
        # Check KYC status
        kyc_request = get_object_or_404(KYCRequest, user=user.userprofile)
        if kyc_request.status != 'approved':
            return {'error': 'KYC verification is not approved.'}

        try:
            # Create withdrawal transaction through Polaris
            transaction = create_transaction(
                asset_code="USDC",
                account=settings.STELLAR_PLATFORM_PUBLIC_KEY,  # Use the single custody account
                amount=str(amount),
                kind="withdrawal"
            )

            # Record the transaction in your system's ledger
            Transaction.objects.create(
                user=user,
                amount=amount,
                transaction_type='withdrawal',
                status='pending',
                external_transaction_id=transaction.id
            )

            return {
                'status': 'initiated',
                'transaction_id': transaction.id,
                'more_info_url': transaction.more_info_url  # URL to Polaris interactive flow
            }

        except Exception as e:
            return {'error': str(e)}

    def check_transaction_status(self, transaction_id):
        try:
            # Use Polaris to check the status of a transaction
            transaction = get_transaction(transaction_id)

            # If the transaction is completed, update the user's balance
            if transaction.status == "completed":
                local_transaction = Transaction.objects.get(external_transaction_id=transaction_id)
                if local_transaction.transaction_type == 'deposit':
                    self.update_balance(local_transaction.user, Decimal(transaction.amount_in), 'deposit')
                elif local_transaction.transaction_type == 'withdrawal':
                    self.update_balance(local_transaction.user, Decimal(transaction.amount_in), 'withdrawal')

            return {
                'status': transaction.status,
                'amount': transaction.amount_in,
                'transaction_id': transaction.id
            }
        except Exception as e:
            return {'error': str(e)}

    def update_balance(self, user, amount, transaction_type):
        """Update user's USDAccount balance based on transaction type."""
        usd_account = user.usd_account
        if transaction_type == 'deposit':
            usd_account.deposit(amount)
        elif transaction_type == 'withdrawal':
            usd_account.withdraw(amount)