import logging
from urllib.parse import urlencode
from rest_framework.response import Response
import requests
from rest_framework import status
from rest_framework.utils import timezone
from stellar_sdk import Server, Asset
from decimal import Decimal
from django.conf import settings
import uuid

from app.models import Transaction, USDAccount, PlatformAccount
from app.services.transact.utils.utils import get_state_code

logger = logging.getLogger(__name__)


class DepositService:
    def __init__(self, user):
        self.user = user
        self.usd_account = USDAccount.objects.get(user=user)
        self.platform_account = PlatformAccount.objects.first()
        self.stellar_server = Server("https://horizon.stellar.org")

        self.api_key = settings.CIRCLE_API
        self.headers = {
            'accept': 'application/json',
            'authorization': f'Bearer {self.api_key}',
            'content-type': 'application/json'
        }

    @staticmethod
    def is_valid_payment_method(payment_method):
        allowed_payment_methods = [
            "sepa", "Faster Payment Bank Transfer", "Open Banking", "maya", "bpi",
            "grabpay", "shopeepay", "gcash", "pix", "astropay",
            "pse", "impa", "upi", "wire", "apple pay", "gpay"
        ]
        return payment_method in allowed_payment_methods

    # Stellar-USDC direct deposit method with pooled account
    def initiate_usdc_deposit(self, amount):
        # Generate a unique memo for this deposit
        memo = str(uuid.uuid4())[:12]  # Use first 12 characters for better uniqueness

        # Create a pending deposit record
        pending_deposit = Transaction.objects.create(
            user=self.user,
            amount=Decimal(amount),
            memo=memo,
            status='pending'
        )

        # Prepare deposit instructions
        instructions = {
            "amount": amount,
            "asset": "USDC",
            "destination_address": settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT,
            "memo": memo,
            "memo_type": "text"
        }

        return instructions, pending_deposit.id

    def confirm_usdc_deposit(self, pending_deposit_id):
        pending_deposit = Transaction.objects.get(id=pending_deposit_id)

        if pending_deposit.status != 'pending':
            return {"status": "error", "message": "This deposit is no longer pending."}

        # Check for the payment on the Stellar network
        payments = self.stellar_server.payments().for_account(settings.PLATFORM_STELLAR_ADDRESS).include_failed(
            False).limit(50).order(desc=True).call()

        usdc_asset = Asset("USDC", settings.USDC_ISSUER_PUBLIC_KEY)

        for payment in payments['_embedded']['records']:
            if (payment['type'] == 'payment' and
                    payment['to'] == settings.PLATFORM_STELLAR_ADDRESS and
                    payment['asset_type'] == 'credit_alphanum4' and
                    payment['asset_code'] == 'USDC' and
                    payment['asset_issuer'] == settings.USDC_ISSUER_PUBLIC_KEY and
                    float(payment['amount']) == float(pending_deposit.amount) and
                    payment.get('memo') == pending_deposit.memo):
                # Payment found, process the deposit
                usdc_amount = Decimal(payment['amount'])
                self.usd_account.credit(usdc_amount)  # Credit user's virtual balance
                self.platform_account.credit(usdc_amount)  # Increase the platform USDC balance

                # Update the pending deposit
                pending_deposit.status = 'completed'
                pending_deposit.stellar_transaction_id = payment['transaction_hash']
                pending_deposit.save()

                # Create a completed transaction record
                Transaction.objects.create(
                    user=self.user,
                    amount=usdc_amount,
                    transaction_type='USDC deposit',
                    status='completed',
                    stellar_transaction_id=payment['transaction_hash']
                )

                return {"status": "success", "message": "Deposit confirmed and processed."}

        # If we've checked all recent payments and haven't found the deposit
        return {"status": "pending", "message": "Deposit not yet detected. Please try confirming again later."}

    def reconcile_memo_less_deposit(self, sender_address, amount):
        # Convert amount to Decimal for precise comparison
        amount = Decimal(str(amount))

        # Look for pending deposits matching the amount
        matching_deposits = Transaction.objects.filter(
            user=self.user,
            amount=amount,
            status='pending'
        ).order_by('-created_at')

        if not matching_deposits.exists():
            return {"status": "error", "message": "No matching pending deposit found."}

        # Check for the payment on the Stellar network
        payments = self.stellar_server.payments().for_account(settings.PLATFORM_STELLAR_ADDRESS).include_failed(
            False).limit(200).order(desc=True).call()

        usdc_asset = Asset("USDC", settings.USDC_ISSUER_PUBLIC_KEY)

        for payment in payments['_embedded']['records']:
            if (payment['type'] == 'payment' and
                    payment['from'] == sender_address and
                    payment['to'] == settings.PLATFORM_STELLAR_ADDRESS and
                    payment['asset_type'] == 'credit_alphanum4' and
                    payment['asset_code'] == 'USDC' and
                    payment['asset_issuer'] == settings.USDC_ISSUER_PUBLIC_KEY and
                    Decimal(payment['amount']) == amount):
                # Payment found, process the deposit
                usdc_amount = Decimal(payment['amount'])
                self.usd_account.credit(usdc_amount)  # Credit user's virtual balance
                self.platform_account.credit(usdc_amount)  # Increase the platform USDC balance

                # Update the pending deposit
                pending_deposit = matching_deposits.first()
                pending_deposit.status = 'completed'
                pending_deposit.stellar_transaction_id = payment['transaction_hash']
                pending_deposit.reconciled_at = timezone.now()
                pending_deposit.save()

                # Create a completed transaction record
                Transaction.objects.create(
                    user=self.user,
                    amount=usdc_amount,
                    transaction_type='USDC deposit (reconciled)',
                    status='completed',
                    stellar_transaction_id=payment['transaction_hash']
                )

                return {"status": "success", "message": "Deposit reconciled and processed."}

        # If we've checked all recent payments and haven't found the deposit
        return {"status": "error", "message": "No matching transaction found on the Stellar network."}

    def list_unreconciled_deposits(self, days_back=30):
        # Find recent payments without memos
        end_time = timezone.now()
        start_time = end_time - timezone.timedelta(days=days_back)

        payments = self.stellar_server.payments().for_account(settings.PLATFORM_STELLAR_ADDRESS).include_failed(
            False).order(desc=True).call()

        unreconciled_deposits = []

        for payment in payments['_embedded']['records']:
            payment_time = timezone.datetime.strptime(payment['created_at'], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            if payment_time < start_time:
                break

            if (payment['type'] == 'payment' and
                    payment['to'] == settings.PLATFORM_STELLAR_ADDRESS and
                    payment['asset_type'] == 'credit_alphanum4' and
                    payment['asset_code'] == 'USDC' and
                    payment['asset_issuer'] == settings.USDC_ISSUER_PUBLIC_KEY and
                    not payment.get('memo')):
                unreconciled_deposits.append({
                    'from': payment['from'],
                    'amount': payment['amount'],
                    'transaction_hash': payment['transaction_hash'],
                    'created_at': payment['created_at']
                })

        return unreconciled_deposits

    # Transak deposit method with pooled account
    def transak_deposit(self, amount, fiat_currency, payment_method, crypto_currency="USDC", network="stellar"):
        # Define the Transak API endpoint
        url = "https://api-stg.transak.com/v1.0/transaction"

        # Parameters for the transaction
        params = {
            "fiatAmount": amount,
            "fiatCurrency": fiat_currency,
            "cryptoCurrencyCode": crypto_currency,
            "apiKey": settings.TRANSAK_API_KEY,
            "productsAvailed": "BUY",
            "network": network,
            "paymentMethod": payment_method,
            "hideExchangeScreen": True
        }

        # Generate the URL with pre-filled data for the checkout page
        checkout_url = f"{url}?{urlencode(params)}"
        return checkout_url

    # Circle bank transfer method
    def circle_bank_transfer(self, amount):
        # Step 1: Link the bank account
        try:
            bank_account_id = self.link_bank_account()
            if not bank_account_id:
                return Response({"status": "error", "message": "Bank account linking failed."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Step 2: Get wire instructions for the bank account
            wire_instructions = self.get_wire_instructions(bank_account_id)
            if not wire_instructions:
                return Response({"status": "error", "message": "Failed to get wire instructions."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Step 3: Notify the user to proceed with the transfer
            return Response({
                "status": "success",
                "message": "Bank account linked successfully. Please use the following wire instructions to transfer funds.",
                "wire_instructions": wire_instructions
            })
        except Exception as e:
            logger.error(f"Error in bank transfer process: {e}")
            return Response({"status": "error", "message": "An error occurred during the transfer process."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def link_bank_account(self):
        try:
            # Get user's profile information
            profile = self.user.userprofile  # Access the related UserProfile

            # Convert state name to 2-character code
            state_code = get_state_code(profile.state)

            url = "https://api-sandbox.circle.com/v1/businessAccount/banks/wires"
            params = {
                "billingDetails": {
                    "name": profile.full_name,
                    "city": profile.city,
                    "country": profile.country.code if profile.country else "US",
                    "line1": profile.address,
                    "district": state_code,  # The 2-character state code
                    "postalCode": "00000"  # Placeholder for postal code
                },
                "bankAddress": {
                    "bankName": "WELLS FARGO BANK, NA",
                    "city": "SAN FRANCISCO",
                    "country": "US",
                    "line1": "100 Money Street",
                    "district": "CA"  # Bank's state
                },
                "idempotencyKey": str(uuid.uuid4()),  # Unique key for retries
                "accountNumber": "12340010",  # Sample account number (replace with actual data)
                "routingNumber": "121000248"  # Sample routing number (replace with actual data)
            }

            # Send request to Circle API
            response = requests.post(url, headers=self.headers, json=params, timeout=30)
            response.raise_for_status()  # Raise an error for bad responses

            data = response.json()
            if data.get("data"):
                return data["data"]["id"]  # Return the bank account ID
            else:
                logger.error(f"Unexpected response structure: {data}")
                return None

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {response.text}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Bank account linking failed: {e}")
            return None
        except AttributeError:
            logger.error("UserProfile not found for the given user.")
            return None

    def get_wire_instructions(self, bank_account_id):
        """
        Step 2: Get wire instructions using the linked bank account ID.
        """
        try:
            url = f"https://api-sandbox.circle.com/v1/businessAccount/banks/wires/{bank_account_id}/instructions?currency=USD"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("data"):
                return data["data"]  # Return the wire instructions details
            else:
                logger.error(f"Unexpected response structure: {data}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get wire instructions: {e}")
            return None

    # MoneyGram deposit method
    def moneygram_deposit(self, reference_id):
        url = f"https://api.stellar.org/moneygram/transactions/{reference_id}"
        response = requests.get(url)
        data = response.json()
        if data.get("status") == "COMPLETED":
            usdc_amount = Decimal(data.get("amount"))
            self.usd_account.credit(usdc_amount)  # Credit the user's virtual balance
            self.platform_account.credit(usdc_amount)  # Increase the platform balance
            Transaction.objects.create(
                user=self.user,
                amount=usdc_amount,
                transaction_type='MoneyGram deposit',
                status='completed'
            )
            return usdc_amount
        return None