from django.db.models import Sum
from django.core.mail import send_mail
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class ReconciliationService:
    def __init__(self, pooled_account_api):
        self.pooled_account_api = pooled_account_api

    def get_total_ledger_balance(self):
        """Calculate the sum of all user balances from USDAccount models."""
        return USDAccount.objects.aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')

    def get_actual_pooled_balance(self):
        """Retrieve the current balance of the actual pooled account."""
        return self.pooled_account_api.get_balance()

    def reconcile(self, tolerance=Decimal('0.01')):
        """
        Perform the reconciliation process.
        
        Args:
            tolerance (Decimal): The maximum acceptable difference between ledger and actual balance.
        
        Returns:
            bool: True if reconciliation is successful, False otherwise.
        """
        total_ledger_balance = self.get_total_ledger_balance()
        actual_pooled_balance = self.get_actual_pooled_balance()

        difference = abs(total_ledger_balance - actual_pooled_balance)

        if difference > tolerance:
            self._handle_discrepancy(total_ledger_balance, actual_pooled_balance, difference)
            return False
        else:
            logger.info(f"Reconciliation successful. "
                        f"Ledger total: ${total_ledger_balance}, "
                        f"Actual pool: ${actual_pooled_balance}")
            return True

    def _handle_discrepancy(self, ledger_balance, actual_balance, difference):
        """Handle cases where a significant discrepancy is found."""
        error_message = (f"Discrepancy detected: "
                         f"Ledger total ${ledger_balance}, "
                         f"Actual pool ${actual_balance}. "
                         f"Difference: ${difference}")
        
        logger.error(error_message)
        
        # Send alert email
        send_mail(
            subject="URGENT: Account Reconciliation Discrepancy",
            message=error_message,
            from_email="system@yourcompany.com",
            recipient_list=["finance@yourcompany.com", "tech@yourcompany.com"],
            fail_silently=False,
        )

        # Here you might also want to trigger other alert mechanisms
        # such as SMS, Slack notification, etc.

def run_daily_reconciliation():
    """Function to be called by your task scheduler (e.g., Celery) for daily reconciliation."""
    pooled_account_api = YourPooledAccountAPI()  # You need to implement this
    reconciliation_service = ReconciliationService(pooled_account_api)
    reconciliation_service.reconcile()

# Usage in your task scheduler (e.g., Celery):
# @celery.task
# def scheduled_reconciliation():
#     run_daily_reconciliation()

# For manual reconciliation
if __name__ == "__main__":
    run_daily_reconciliation()