import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.db import transaction
from django.core.exceptions import ValidationError
from app.models import USDAccount
from invest.models import Portfolio, Transaction
from invest.transact import send_funds_from_stellar, withdraw_funds_to_stellar
import requests

# Initialize logger
logger = logging.getLogger(__name__)


# Helper functions
def validate_amount(amount):
    """
    Validates the amount ensuring it's a positive number.

    :param amount: The amount to validate.
    :raises ValidationError: If the amount is invalid or not positive.
    :return: The validated float amount.
    """
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValidationError("Amount must be a positive number")
    except (TypeError, ValueError) as e:
        logger.error(f"Amount validation failed: {e}")
        raise ValidationError("Invalid amount format")
    return amount


def create_alpaca_portfolio():
    """
    Creates a new Alpaca portfolio by calling the Alpaca API.

    :return: Alpaca account ID if successful, otherwise returns an error message.
    """
    alpaca_api_url = "https://paper-api.alpaca.markets/v2/accounts"
    headers = {
        'APCA-API-KEY-ID': '<your-api-key>',
        'APCA-API-SECRET-KEY': '<your-api-secret>',
    }

    try:
        response = requests.post(alpaca_api_url, headers=headers)
        response.raise_for_status()
        return response.json().get('account_id'), None
    except requests.RequestException as e:
        logger.error(f"Alpaca account creation failed: {e}")
        return None, str(e)


# Views
@api_view(['POST'])
def create_portfolio(request):
    """
    API endpoint to create a new portfolio for a user by calling the Alpaca API.

    :param request: The request object containing the user information.
    :return: Response with portfolio_id if successful, otherwise returns an error message.
    """
    user = request.user

    alpaca_account_id, error = create_alpaca_portfolio()
    if error:
        logger.error(f"Error during portfolio creation: {error}")
        return Response({'error': f'Alpaca account creation failed: {error}'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        portfolio = Portfolio.objects.create(user=user, alpaca_account_id=alpaca_account_id)
        logger.info(f"Portfolio created for user {user.id} with portfolio ID {portfolio.id}")
        return Response({'portfolio_id': portfolio.id}, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error saving portfolio to database: {e}")
        return Response({'error': 'Failed to create portfolio'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def credit_portfolio(request):
    """
    API endpoint to credit a user's portfolio from their USD virtual wallet.

    :param request: The request object containing user and amount details.
    :return: Response with updated portfolio balance if successful, otherwise returns an error message.
    """
    user = request.user
    amount = request.data.get('amount')

    try:
        amount = validate_amount(amount)  # Validate amount
    except ValidationError as e:
        logger.error(f"Validation error during portfolio credit: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        wallet = USDAccount.objects.get(user=user)
    except USDAccount.DoesNotExist:
        logger.error(f"User wallet not found for user {user.id}")
        return Response({'error': 'User wallet not found'}, status=status.HTTP_404_NOT_FOUND)

    if wallet.balance < amount:
        logger.warning(
            f"Insufficient balance for user {user.id}: Wallet balance is {wallet.balance}, required {amount}")
        return Response({'error': 'Insufficient wallet balance'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            transfer_response = send_funds_from_stellar(amount, user)

            if not transfer_response.get('success'):
                logger.error(f"Failed to send funds from Stellar for user {user.id}: {transfer_response.get('error')}")
                return Response({'error': transfer_response.get('error')}, status=status.HTTP_400_BAD_REQUEST)

            portfolio = Portfolio.objects.get(user=user)
            portfolio.balance += amount
            portfolio.save()

            Transaction.objects.create(user=user, amount=amount, transaction_type='credit')

            wallet.balance -= amount
            wallet.save()

            logger.info(
                f"Successfully credited portfolio for user {user.id}. New portfolio balance: {portfolio.balance}")
            return Response({'balance': portfolio.balance}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Transaction failed for user {user.id}: {e}")
        return Response({'error': 'Credit transaction failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def withdraw_from_portfolio(request):
    """
    API endpoint to withdraw funds from a user's portfolio to their Stellar account.

    :param request: The request object containing user and amount details.
    :return: Response with updated portfolio balance if successful, otherwise returns an error message.
    """
    user = request.user
    amount = request.data.get('amount')

    try:
        amount = validate_amount(amount)  # Validate amount
    except ValidationError as e:
        logger.error(f"Validation error during portfolio withdrawal: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    portfolio = Portfolio.objects.get(user=user)

    if portfolio.balance < amount:
        logger.warning(
            f"Insufficient portfolio balance for user {user.id}: Portfolio balance is {portfolio.balance}, required {amount}")
        return Response({'error': 'Insufficient portfolio balance'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            withdrawal_response = withdraw_funds_to_stellar(amount, user)

            if not withdrawal_response.get('success'):
                logger.error(f"Withdrawal failed for user {user.id}: {withdrawal_response.get('error')}")
                return Response({'error': f"Withdrawal failed: {withdrawal_response.get('error')}"},
                                status=status.HTTP_400_BAD_REQUEST)

            portfolio.balance -= amount
            portfolio.save()

            Transaction.objects.create(user=user, amount=amount, transaction_type='withdraw')

            logger.info(
                f"Successfully withdrew {amount} from portfolio for user {user.id}. New balance: {portfolio.balance}")
            return Response({'balance': portfolio.balance}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Withdrawal transaction failed for user {user.id}: {e}")
        return Response({'error': 'Withdrawal transaction failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Placeholder for Alpaca withdrawal
def withdraw_funds_from_alpaca(user, amount):
    """
    Sends a request to Alpaca API to withdraw funds from a user's Alpaca account.

    :param user: The user object.
    :param amount: The amount to withdraw.
    :return: Success status and any errors if applicable.
    """
    alpaca_api_url = f"https://paper-api.alpaca.markets/v2/accounts/{user.portfolio.alpaca_account_id}/withdrawals"
    headers = {
        'APCA-API-KEY-ID': '<your-api-key>',
        'APCA-API-SECRET-KEY': '<your-api-secret>',
    }
    data = {
        'amount': amount,
        'currency': 'USD'
    }

    try:
        response = requests.post(alpaca_api_url, headers=headers, json=data)
        response.raise_for_status()
        return {'success': True}
    except requests.RequestException as e:
        logger.error(f"Failed to withdraw funds from Alpaca for user {user.id}: {e}")
        return {'success': False, 'error': str(e)}
