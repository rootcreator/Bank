from polaris.sep24.transaction import create_transaction, get_transaction
from app.models import Transaction, UserProfile
from kyc.models import KYCRequest
from django.conf import settings
from django.shortcuts import get_object_or_404

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
            # Handle and log errors
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
            # Handle and log errors
            return {'error': str(e)}

    def check_transaction_status(self, transaction_id):
        try:
            # Use Polaris to check the status of a transaction
            transaction = get_transaction(transaction_id)
            return {
                'status': transaction.status,
                'amount': transaction.amount_in,
                'transaction_id': transaction.id
            }
        except Exception as e:
            return {'error': str(e)}