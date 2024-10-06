from celery import shared_task
from .views import process_kyc

@shared_task
def async_process_kyc(kyc_request_id):
    from .models import KYCRequest  # Import here to avoid circular import
    kyc_request = KYCRequest.objects.get(id=kyc_request_id)
    process_kyc(kyc_request)