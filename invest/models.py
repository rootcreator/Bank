from django.db import models
from app.models import User


class Portfolio(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    alpaca_account_id = models.CharField(max_length=100)  # Store Alpaca account ID
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invest_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10)  # 'credit' or 'withdraw'
    timestamp = models.DateTimeField(auto_now_add=True)
