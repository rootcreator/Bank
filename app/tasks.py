import celery

from app.services.reconciliation import run_daily_reconciliation


@celery.task
def scheduled_reconciliation():
    run_daily_reconciliation()