import logging
from email.message import EmailMessage

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django_countries import countries
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.views import TokenObtainPairView

from kyc.models import KYCRequest
from kyc.serializers import KYCRequestSerializer
from kyc.tasks import async_process_kyc  # Import the Celery task
from . import serializers
from .models import Transaction, USDAccount
from .models import UserProfile, Region  # Ensure to import the Region model
from .serializers import UserSerializer, UserProfileSerializer, USDAccountSerializer, TransactionSerializer
from .services.stellar_anchor_service import StellarAnchorService
from .services.transact import DepositService, WithdrawalService, TransferService

logger = logging.getLogger(__name__)

User = get_user_model()


class InsufficientFundsError(Exception):
    pass


def get_country_code(country_name):
    for code, name in dict(countries).items():
        if name.lower() == country_name.lower():
            return code
    return None


# Registration
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    try:
        with transaction.atomic():
            user_data = {
                'username': request.data.get('username'),
                'email': request.data.get('email'),
                'password': request.data.get('password')
            }
            profile_data = request.data.get('profile', {})

            logger.info(f"Incoming registration data: {user_data}")

            # Validate and create user
            user_serializer = UserSerializer(data=user_data)
            if not user_serializer.is_valid():
                logger.error(f"User serializer errors: {user_serializer.errors}")
                return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            user = user_serializer.save()

            # Handle region
            region_name = profile_data.get('region')
            if region_name:
                try:
                    region = Region.objects.get(name=region_name)
                    profile_data['region'] = region.id
                except Region.DoesNotExist:
                    user.delete()  # Rollback user creation
                    return Response({"error": f"Invalid region: {region_name}"}, status=status.HTTP_400_BAD_REQUEST)

            # Handle country
            country_name = profile_data.get('country')
            if country_name:
                country_code = get_country_code(country_name)
                if country_code:
                    profile_data['country'] = country_code
                else:
                    user.delete()  # Rollback user creation
                    return Response({"error": f"Invalid country: {country_name}"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate profile data
            profile_serializer = UserProfileSerializer(data=profile_data)
            if not profile_serializer.is_valid():
                logger.error(f"Profile serializer errors: {profile_serializer.errors}")
                user.delete()  # Rollback user creation
                return Response(profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Create UserProfile
            profile = profile_serializer.save(user=user)

            # Create USD account
            usd_account = USDAccount.objects.create(user=user, balance=0.0)

            return Response({
                'user': UserSerializer(user).data,
                'profile': UserProfileSerializer(profile).data,
                'usd_account': {'id': usd_account.id, 'balance': usd_account.balance},
            }, status=status.HTTP_201_CREATED)

    except IntegrityError as e:
        logger.error(f"IntegrityError during user registration: {str(e)}")
        return Response({'error': 'A unique constraint error occurred'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Unexpected error during user registration: {str(e)}")
        return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper function for email verification (optional)
def send_verification_email(request, user):
    current_site = get_current_site(request)
    mail_subject = 'Activate your account.'
    message = render_to_string('acc_active_email.html', {
        'user': user,
        'domain': current_site.domain,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        # No activation token needed anymore
    })
    email = EmailMessage(mail_subject, message, to=[user.email])
    email.send()


def validate_user_data(data):
    if User.objects.filter(email=data['email']).exists():
        raise serializers.ValidationError("A user with this email already exists.")

    try:
        validate_password(data['password'])
    except ValidationError as e:
        raise serializers.ValidationError({"password": list(e.messages)})


# Login
class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Logout
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout a user by blacklisting the token."""
    try:
        # Get the token from the request
        token = request.auth
        # Blacklist the token
        BlacklistedToken.objects.create(token=token)
        return Response({"message": "Logged out successfully."}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Reset Auth
@api_view(['POST'])
def password_reset_request(request):
    email = request.data.get("email")
    if not email:
        return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User with this email does not exist"}, status=status.HTTP_404_NOT_FOUND)

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    reset_link = f"http://yourfrontend.com/reset-password/{uid}/{token}/"  # Adjust based on your frontend
    message = render_to_string('password_reset_email.html', {'reset_link': reset_link})

    send_mail(
        'Password Reset Request',
        message,
        'no-reply@yourdomain.com',  # Replace with your email
        [email],
        fail_silently=False,
    )

    return Response({"message": "Password reset email sent"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def password_reset_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        new_password = request.data.get("new_password")
        if not new_password:
            return Response({"error": "New password is required"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password has been reset successfully"}, status=status.HTTP_200_OK)

    return Response({"error": "Invalid token or user ID"}, status=status.HTTP_400_BAD_REQUEST)


# KYC Update View
@api_view(['PUT'])
@permission_classes([IsAuthenticated])  # Ensure user is authenticated
def update_kyc_status(request):
    try:
        user = request.user
        profile = user.userprofile
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully", "data": serializer.data},
                            status=status.HTTP_200_OK)

        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except UserProfile.DoesNotExist:
        return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)


def create_kyc_request(profile, user):
    # Create a new KYCRequest
    KYCRequest.objects.create(
        user=profile,  # Use the UserProfile instance
        full_name=user.get_full_name(),
        date_of_birth=profile.date_of_birth,
        address=profile.address,
        status='pending'
    )


class KYCSubmissionView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def post(self, request):
        serializer = KYCRequestSerializer(data=request.data)

        if serializer.is_valid():
            kyc_request = KYCRequest.objects.create(
                user_profile=request.user.userprofile,
                document_type=serializer.validated_data['document_type'],
                id_document=serializer.validated_data['document_file'],
                address_document=serializer.validated_data['address_proof_file'],
                selfie=serializer.validated_data['selfie_file'],
                status='pending'
            )

            async_process_kyc.delay(kyc_request.id)  # Trigger the Celery task

            logger.info(f"KYC submitted successfully for user {request.user.id}. Task ID: {kyc_request.id}")
            return Response({"message": "KYC submitted successfully, pending approval."},
                            status=status.HTTP_201_CREATED)

        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class KYCStatusView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure user is authenticated

    @staticmethod
    def get(request):
        user_profile = request.user.userprofile  # Get the UserProfile object from the user

        try:
            # Fetch KYCRequest using the correct user_profile
            kyc_request = KYCRequest.objects.get(user_profile=user_profile)
            return Response({"kyc_status": kyc_request.status}, status=status.HTTP_200_OK)

        except KYCRequest.DoesNotExist:
            return Response({"error": "KYC request not found"}, status=status.HTTP_404_NOT_FOUND)


def process_kyc_for_user(user_profile):
    """Processes KYC verification for a given user."""
    try:
        # Fetch the KYC request related to the user profile
        kyc_request = KYCRequest.objects.get(user_profile=user_profile)

        # Call the KYC verification logic (Assuming verify is a method in the KYCRequest model)
        kyc_status = kyc_request.verify()  # If 'verify' is a static or instance method

        # Update the status in KYCRequest model
        kyc_request.status = kyc_status
        kyc_request.save()

        logger.info(f"KYC verification succeeded for user {user_profile.id}. Status: {kyc_status}")
        return kyc_status

    except KYCRequest.DoesNotExist:
        logger.error(f"KYC request not found for user {user_profile.id}.")
        return "KYC request not found"

    except Exception as e:
        # Log the error and raise an appropriate message
        logger.error(f"KYC verification failed for user {user_profile.id}: {str(e)}")
        raise  # Reraise or handle as necessary


# Account
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_view(request):
    """Retrieve the user's account details."""
    user = request.user
    usd_account = get_object_or_404(USDAccount, user=user)
    return Response(USDAccountSerializer(usd_account).data, status=status.HTTP_200_OK)


# Balance
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def balance_view(request):
    """Retrieve the user's USD balance."""
    user = request.user
    usd_account = get_object_or_404(USDAccount, user=user)
    return Response({'balance': usd_account.balance}, status=status.HTTP_200_OK)


# Transaction History
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_view(request):
    """Retrieve a list of transactions for the user."""
    user = request.user
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Deposit
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_deposit(request):
    user = request.user
    amount = request.data.get('amount')

    if not amount:
        return Response({'error': 'Amount is required'}, status=status.HTTP_400_BAD_REQUEST)

    # Ensure token exists or create one for the user
    token, created = Token.objects.get_or_create(user=user)

    deposit_service = DepositService()
    result = deposit_service.initiate_deposit(user, amount)

    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    if 'error' in result:
        logger.error(f"Deposit failed for user {user.id}: {result['error']}")
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    logger.info(f"Deposit initiated for user {user.id}: {result['transaction_id']}")

    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
def deposit_callback(request):
    # This endpoint would be called by the anchor
    callback_data = request.data
    deposit_service = DepositService()
    result = deposit_service.process_deposit_callback(callback_data)
    return Response(result, status=200)


# Withdraw
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_withdrawal(request):
    user = request.user
    amount = request.data.get('amount')

    if not amount:
        return Response({'error': 'Amount is required'}, status=status.HTTP_400_BAD_REQUEST)

    withdrawal_service = WithdrawalService()
    result = withdrawal_service.initiate_withdrawal(user, amount)

    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
def withdrawal_callback(request):
    # This endpoint would be called by the anchor for withdrawal callbacks
    callback_data = request.data
    withdrawal_service = WithdrawalService()
    result = withdrawal_service.process_withdrawal_callback(callback_data)
    return Response(result, status=200)


# Transfers
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_transfer(request):
    sender = request.user
    recipient_username = request.data.get("recipient")
    amount = request.data.get("amount")

    try:
        amount = float(amount)  # Ensure amount is a float for validation
    except (ValueError, TypeError):
        return Response({"error": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        recipient = User.objects.get(username=recipient_username)
    except User.DoesNotExist:
        return Response({"error": "Recipient not found."}, status=status.HTTP_404_NOT_FOUND)

    transfer_service = TransferService()

    try:
        result = transfer_service.process_internal_transfer(sender, recipient, amount)

        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Transfer successful"}, status=status.HTTP_200_OK)

    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except InsufficientFundsError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Unexpected error during transfer: {e}")
        return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Transaction Status
@api_view(['GET'])
def transaction_status(request, transaction_id):
    logger.info(f"Checking status for transaction {transaction_id}")

    # Instantiate the StellarAnchorService
    anchor_service = StellarAnchorService()

    # Check the transaction status
    status_response = anchor_service.check_transaction_status(transaction_id)

    # Check if the response contains a valid status
    if "error" not in status_response:
        return Response(status_response, status=status.HTTP_200_OK)

    return Response({
        "error": "Transaction not found or failed."
    }, status=status.HTTP_404_NOT_FOUND)


# Payment Webhooks
@api_view(['POST'])
def payment_webhook(request, provider):
    # Handle webhook from different providers
    if provider == "flutterwave":
        # Process the Flutterwave webhook
        pass
    elif provider == "tempo":
        # Process the Tempo webhook
        pass
    elif provider == "moneygram":
        # Process the Tempo webhook
        pass
    elif provider == "circle":
        data = request.data
        payment_id = data.get('id')
        status = data.get('status')

        # Update the transaction status in your database

    elif provider == "settle_network":
        # Process the Tempo webhook
        pass
    elif provider == "alchemy_pay":
        # Process the Tempo webhook
        pass

    try:
        txn = Transaction.objects.get(id=payment_id)
        transaction.status = status  # Update to 'completed', 'pending', etc.
        transaction.save()
        return Response({"message": "Transaction status updated."}, status=status.HTTP_200_OK)
    except Transaction.DoesNotExist:
        return Response({"error": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)


# Service Status
@api_view(['GET'])
def health_check(request):
    """Check the health of the service."""
    return Response({"status": "healthy"}, status=status.HTTP_200_OK)
