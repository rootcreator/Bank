from datetime import timedelta
from django.utils import timezone
from app.models import Transaction, Alert


class TransactionMonitor:
    def __init__(self, transaction):
        self.transaction = transaction

    def is_large_transaction(self):
        # Example rule: transactions over $10,000
        return self.transaction.amount > 10000

    def is_high_frequency(self):
        # Example rule: More than 5 transactions within 10 minutes
        recent_transactions = Transaction.objects.filter(
            user=self.transaction.user,
            timestamp__gte=timezone.now() - timedelta(minutes=10)
        )
        return recent_transactions.count() > 5

    def is_high_risk_country(self):
        # Example rule: Transaction from a high-risk country
        high_risk_countries = ['Country1', 'Country2']
        return self.transaction.geolocation in high_risk_countries

    def run_rules(self):
        flags = []
        if self.is_large_transaction():
            flags.append("Large transaction")
        if self.is_high_frequency():
            flags.append("High frequency of transactions")
        if self.is_high_risk_country():
            flags.append("Transaction from high-risk country")

        return flags


def monitor_transaction(transaction):
    '''
    This function monitors a transaction, checks if it violates any rules,
    and creates an alert if necessary.
    '''
    monitor = TransactionMonitor(transaction)
    flags = monitor.run_rules()

    if flags:
        # Log the alert
        Alert.objects.create(transaction=transaction, flags=flags)
        # Notify admin (this could be an email or a system alert)
        send_admin_notification(transaction, flags)


def send_admin_notification(transaction, flags):
    '''
    Mock function to send a notification to the admin
    when a suspicious transaction is detected.
    '''
    # Logic to send an alert (e.g., via email or system notification) to the admin
    print(f"Admin notified: Suspicious transaction {transaction.id} with flags: {flags}")
