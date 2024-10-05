from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from app.models import UserProfile
from .models import KYCRequest
from .services import verify_id, verify_address, run_aml_check, send_approval_notification, verify_faces


def submit_kyc(request):
    if request.method == 'POST':
        user_profile = get_object_or_404(UserProfile, user=request.user)

        # Save KYC request
        kyc_request = KYCRequest.objects.create(
            user_profile=user_profile,
            id_document=request.FILES['id_document'],
            selfie=request.FILES['selfie'],
            address_document=request.FILES['address_document'],
            status='pending'
        )
        process_kyc(kyc_request)
        return JsonResponse({'message': 'KYC submitted successfully!'})


def process_kyc(kyc_request):
    # Step 1: Verify ID
    if not verify_id(kyc_request.id_document, kyc_request.selfie):
        kyc_request.status = 'rejected'
        kyc_request.save()
        return

    # Step 2: Verify Address
    if not verify_address(kyc_request.address_document):
        kyc_request.status = 'rejected'
        kyc_request.save()
        return

    # Step 3: Run AML Check
    if not run_aml_check(kyc_request.user):
        kyc_request.status = 'rejected'
        kyc_request.save()
        return

    # Step 4: Run Face Check
    if not verify_faces(kyc_request.selfie):
        kyc_request.status = 'rejected'
        kyc_request.save()
        return

    # Step 5: Approve KYC
    kyc_request.status = 'approved'
    kyc_request.save()

    # Send notification
    send_approval_notification(kyc_request.user)
