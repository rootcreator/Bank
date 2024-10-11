from celery import shared_task
import logging
from .models import KYCRequest
  # Importing the process function

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def async_process_kyc(self, kyc_request_id):
    from .views import process_kyc
    """
    Asynchronously process the KYC request by its ID.
    """
    try:
        kyc_request = KYCRequest.objects.get(id=kyc_request_id)
        logger.info(f'Starting KYC processing for request ID {kyc_request_id}.')

        # Call the process_kyc function to handle the actual processing
        process_kyc(kyc_request)
        logger.info(f'KYC processing completed for request ID {kyc_request_id}.')

    except KYCRequest.DoesNotExist:
        logger.error(f'KYC request with ID {kyc_request_id} does not exist.')
        self.retry(countdown=60, max_retries=3)  # Retry after 60 seconds, up to 3 times
    except Exception as e:
        logger.error(f'Error processing KYC request ID {kyc_request_id}: {str(e)}')
        self.retry(countdown=60, max_retries=3)  # Retry after 60 seconds for any exception
