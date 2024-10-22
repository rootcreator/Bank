from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
import logging

from rest_framework.decorators import api_view

from .models import KYCRequest
from app.models import UserProfile
from .services import (
    verify_id,
    verify_address,
    run_aml_check,
    send_approval_notification,
    verify_faces,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
def submit_kyc(request):
    from .tasks import async_process_kyc
    if request.method == 'POST':
        user_profile = get_object_or_404(UserProfile, user=request.user)

        # Validate required files
        if not all(
                [request.FILES.get('id_document'), request.FILES.get('selfie'), request.FILES.get('address_document')]):
            return JsonResponse({'error': 'All documents (ID, selfie, address) are required.'}, status=400)

        # Atomic transaction block for KYC request
        try:
            with transaction.atomic():
                # Save KYC request
                kyc_request = KYCRequest.objects.create(
                    user_profile=user_profile,
                    id_document=request.FILES['id_document'],
                    selfie=request.FILES['selfie'],
                    address_document=request.FILES['address_document'],
                    status='pending'
                )
        except Exception as e:
            logger.error(f'Error saving KYC request: {e}')
            return JsonResponse({'error': 'Failed to submit KYC. Please try again.'}, status=500)

        # Start processing the KYC asynchronously using Celery
        async_process_kyc.delay(kyc_request.id)

        return JsonResponse({'message': 'KYC submitted successfully!'}, status=201)


def process_kyc(kyc_request):
    logger.info(f'Starting KYC processing for user {kyc_request.user_profile.user}')

    try:
        # Step 1: Verify KYC
        verification_result = verify_kyc(kyc_request)

        # Step 2: Update KYC status based on verification result
        kyc_request.status = verification_result
        kyc_request.save()

        if verification_result == 'approved':
            logger.info('KYC approved successfully.')
            send_approval_notification(kyc_request.user_profile.user)
        else:
            logger.warning(f'KYC rejected: {verification_result}')
    except Exception as e:
        logger.error(f'Error processing KYC for user {kyc_request.user_profile.user}: {e}')


def verify_kyc(kyc_request):
    """Verify KYC documents and return status."""
    if not verify_id(kyc_request.id_document, kyc_request.selfie):
        return 'rejected: ID verification failed'
    if not verify_address(kyc_request.address_document):
        return 'rejected: Address verification failed'
    if not run_aml_check(kyc_request.user_profile.user):
        return 'rejected: AML check failed'
    if not verify_faces(kyc_request.selfie):
        return 'rejected: Face verification failed'

    return 'approved'


def kyc_status(request):
    """Check the status of the user's KYC request."""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    kyc_request = KYCRequest.objects.filter(user_profile=user_profile).last()

    if kyc_request:
        return JsonResponse({'status': kyc_request.status})
    else:
        return JsonResponse({'status': 'no request found'}, status=404)
