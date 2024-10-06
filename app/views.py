import logging
from email.message import EmailMessage
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator, PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from knox.views import LoginView as KnoxLoginView
from rest_framework import permissions
from rest_framework import status
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from . import serializers
from .models import UserProfile, Transaction, USDAccount
from .serializers import UserSerializer, UserProfileSerializer, USDAccountSerializer, TransactionSerializer
from .services.transact import DepositService, WithdrawalService, TransferService
from .services.stellar_anchor_service import StellarAnchorService
from kyc.serializers import KYCRequestSerializer
from kyc.models import KYCRequest

logger = logging.getLogger(__name__)


# Register
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    with transaction.atomic():
        user_serializer = UserSerializer(data=request.data)
        if user_serializer.is_valid():
            user = user_serializer.save()

            profile_data = request.data.get('profile', {})
            profile_serializer = UserProfileSerializer(data=profile_data)

            if profile_serializer.is_valid():
                profile = profile_serializer.save(user=user)
                usd_account = USDAccount.objects.create(profile=profile, balance=0.0)

                send_verification_email(request, user)

                # Successful registration
                return Response({
                    'user': user_serializer.data,
                    'profile': profile_serializer.data,
                    "is_verified": user.is_verified,
                    'usd_account': {'id': usd_account.id, 'balance': usd_account.balance},
                }, status=status.HTTP_201_CREATED)

            return Response(profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return str(user.pk) + str(timestamp) + (user.is_active or '')


account_activation_token = AccountActivationTokenGenerator()


# Helper function for email verification (if needed)
def send_verification_email(request, user):
    current_site = get_current_site(request)
    mail_subject = 'Activate your account.'
    message = render_to_string('acc_active_email.html', {
        'user': user,
        'domain': current_site.domain,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': account_activation_token.make_token(user),
    })
    email = EmailMessage(mail_subject, message, to=[user.email])
    email.send()


@api_view(['GET'])
@permission_classes([AllowAny])
def activate_account(request, uidb64, token):
    uid = force_str(urlsafe_base64_decode(uidb64))
    user = User.objects.filter(pk=uid).first()

    if user and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        return Response({'message': 'Thank you for your email confirmation. Now you can log in.'},
                        status=status.HTTP_200_OK)

    return Response({'error': 'Activation link is invalid!'}, status=status.HTTP_400_BAD_REQUEST)


def validate_user_data(data):
    if User.objects.filter(email=data['email']).exists():
        raise serializers.ValidationError("A user with this email already exists.")

    try:
        validate_password(data['password'])
    except ValidationError as e:
        raise serializers.ValidationError({"password": list(e.messages)})


# Login
class LoginView(KnoxLoginView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        serializer = AuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)
        return super(LoginView, self).post(request, format=None)


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


logger = logging.getLogger(__name__)

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
            return Response({"message": "Profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except UserProfile.DoesNotExist:
        return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)


from kyc.tasks import async_process_kyc  # Import the Celery task

class KYCSubmissionView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def post(self, request):
        serializer = KYCRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            # Save the KYC data to your KYC model
            kyc_request = KYCRequest.objects.create(
                user_profile=request.user.userprofile,
                document_type=serializer.validated_data['document_type'],
                id_document=serializer.validated_data['document_file'],
                address_document=serializer.validated_data['address_proof_file'],
                selfie=serializer.validated_data['selfie_file'],
                status='pending'  # Start with pending status
            )

            # Start processing the KYC asynchronously
            async_process_kyc.delay(kyc_request.id)  # Trigger the Celery task
            
            logger.info(f"KYC submitted successfully for user {request.user.id}. Task ID: {kyc_request.id}")
            return Response({"message": "KYC submitted successfully, pending approval."},
                            status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class KYCStatusView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure user is authenticated

    def get(self, request):
        user = request.user
        try:
            kyc_request = KYCRequest.objects.get(user_profile=user.userprofile)
            return Response({"kyc_status": kyc_request.status}, status=status.HTTP_200_OK)
        except KYCRequest.DoesNotExist:
            return Response({"error": "KYC not found"}, status=status.HTTP_404_NOT_FOUND)


def process_kyc_for_user(user):
    """Processes KYC verification for a given user."""
    try:
        kyc_request = KYCRequest.objects.get(user_profile=user.userprofile)
        
        # Call the KYC verification logic (this should be async in production)
        kyc_status = KYCRequest.verify(user)  # Assuming this function exists in KYCRequest

        # Update the KYCRequest object with the KYC status
        kyc_request.status = kyc_status
        kyc_request.save()

        logger.info(f"KYC verification succeeded for user {user.id}. Status: {kyc_status}")
        return kyc_status

    except KYCRequest.DoesNotExist:
        logger.error(f"KYC request not found for user {user.id}.")
        return "KYC request not found"
    except Exception as e:
        # Log the error and raise an appropriate message
        logger.error(f"KYC verification failed for user {user.id}: {str(e)}")
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
def anchor_callback(request):
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

    with transaction.atomic():
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            return Response({"error": "Recipient not found."}, status=status.HTTP_404_NOT_FOUND)

        transfer_service = TransferService()
        result = transfer_service.process_internal_transfer(sender, recipient, amount)

        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "Transfer successful"}, status=status.HTTP_200_OK)


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
        # Process the Tempo webhook
        pass
    elif provider == "settle_network":
        # Process the Tempo webhook
        pass
    elif provider == "alchemy_pay":
        # Process the Tempo webhook
        pass

    return Response({"message": "Webhook processed successfully."}, status=status.HTTP_200_OK)


@api_view(['POST'])
def circle_webhook(request):
    data = request.data
    payment_id = data.get('id')
    status = data.get('status')

    # Update the transaction status in your database
    try:
        transaction = Transaction.objects.get(id=payment_id)
        transaction.status = status  # Update to 'completed', 'pending', etc.
        transaction.save()
        return Response({"message": "Transaction status updated."}, status=status.HTTP_200_OK)
    except Transaction.DoesNotExist:
        return Response({"error": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)
