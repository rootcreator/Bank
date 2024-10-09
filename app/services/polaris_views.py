import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from polaris.sep24.transaction import get_transaction
from app.models import Transaction, USDAccount  # Ensure USDAccount is imported
from decimal import Decimal
from .services import StellarAnchorService  # Import your service for handling updates

@csrf_exempt  # To allow POST requests from external sources
def transaction_webhook(request):
    if request.method == 'POST':
        try:
            # Parse the incoming request data
            data = json.loads(request.body)

            # Verify shared secret for security
            provided_secret = request.headers.get('X-Polaris-Signature')
            expected_secret = settings.POLARIS_WEBHOOK_SECRET
            if not constant_time_compare(provided_secret, expected_secret):
                return JsonResponse({'error': 'Invalid secret'}, status=403)

            # Verify the required fields are present
            transaction_id = data.get('transaction_id')
            if not transaction_id:
                return JsonResponse({'error': 'transaction_id is required'}, status=400)

            # Get the transaction details from Polaris
            transaction = get_transaction(transaction_id)
            if transaction.status == 'completed':
                # Find the corresponding transaction in your local database
                local_transaction = Transaction.objects.get(external_transaction_id=transaction_id)

                # Update the user's balance based on transaction type
                stellar_service = StellarAnchorService()
                if local_transaction.transaction_type == 'deposit':
                    stellar_service.update_balance(local_transaction.user, Decimal(transaction.amount_in), 'deposit')
                elif local_transaction.transaction_type == 'withdrawal':
                    stellar_service.update_balance(local_transaction.user, Decimal(transaction.amount_in), 'withdrawal')

            return JsonResponse({'status': 'success'}, status=200)

        except Transaction.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=404)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)