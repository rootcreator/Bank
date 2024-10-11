import uuid
from django_countries.fields import CountryField
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.db import models, transaction, Sum
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)
TRANSACTION_TYPES = (
    ('deposit', 'Deposit'),
    ('withdrawal', 'Withdrawal'),
    ('transfer', 'Transfer'),
)


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name  # No parentheses


class User(AbstractUser):
    email = models.EmailField(unique=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',  # Change this to avoid clashes
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions_set',  # Change this to avoid clashes
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    # Add any additional fields you need

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=255)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    phone_number = models.CharField(max_length=15)
    date_of_birth = models.DateField(null=True, blank=True)
    id_document = models.FileField(upload_to='kyc_documents/')
    selfie = models.FileField(upload_to='kyc_documents/')
    address = models.CharField(max_length=255)
    address_document = models.FileField(upload_to='kyc_documents/')
    country = CountryField(blank_label='(select country)', null=True, blank=True)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.CASCADE)
    is_kyc_completed = models.BooleanField(default=False)
    kyc_status = models.CharField(
        max_length=50,
        choices=[("pending", "Pending"), ("rejected", "Rejected"), ("approved", "Approved")],
        default="pending"
    )

    def __str__(self):
        return f"{self.user} - {self.kyc_status}"


class USDAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="usd_account")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Store in USD
    created_at = models.DateTimeField(auto_now_add=True)

    def update_balance(self, amount):
        """
        Update the balance of the account.
        Use a positive amount to increase the balance, negative to decrease.
        """
        if amount == 0:
            raise ValidationError("Amount must be non-zero.")

        with transaction.atomic():
            new_balance = self.balance + amount
            if new_balance < 0:
                raise ValidationError("Insufficient balance")

            self.balance = new_balance
            self.save()

    def deposit(self, amount):
        """Credit account with deposit."""
        if amount <= 0:
            raise ValidationError("Deposit amount must be positive.")
        self.update_balance(amount)

    def withdraw(self, amount):
        """Debit account with withdrawal."""
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be positive.")
        self.update_balance(-amount)

    def get_transaction_history(self):
        """Retrieve all transactions for the user's account."""
        return Transaction.objects.filter(user=self.user).order_by('-created_at')

    def __str__(self):
        return f"{self.user} - Balance: ${self.balance}"


class Fee(models.Model):
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    flat_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    percentage_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.transaction_type.capitalize()} Fee"

    def calculate_fee(self, amount):
        # Ensure the amount is a Decimal
        amount = Decimal(amount)
        percentage_cost = (self.percentage_fee / Decimal(100)) * amount
        total_fee = self.flat_fee + percentage_cost
        return total_fee

    @classmethod
    def apply_transaction_fee(cls, transaction_type, amount):
        # Ensure the amount is a Decimal
        amount = Decimal(amount)
        fee = cls.objects.get(transaction_type=transaction_type, is_active=True)
        fee_amount = fee.calculate_fee(amount)
        total_amount = amount + fee_amount
        return total_amount, fee_amount


class Transaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    external_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    internal_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.status}"


class TransactionService:

    @staticmethod
    def process_transaction(user, transaction_type, amount, description=None):
        # Check for valid transaction type
        if transaction_type not in dict(TRANSACTION_TYPES):
            raise ValueError("Invalid transaction type.")

        # Retrieve user's USD account
        account = user.usd_account

        # Apply transaction fees
        total_amount, fee_amount = Fee.apply_transaction_fee(transaction_type, amount)

        # Perform the transaction (e.g., deposit or withdrawal)
        if transaction_type == 'deposit':
            account.deposit(total_amount)
        elif transaction_type == 'withdrawal':
            account.withdraw(total_amount)
        elif transaction_type == 'transfer':
            # Add your transfer logic here (between users)
            pass

        # Record the transaction in the history
        transaction = Transaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            fee_amount=fee_amount,
            status='pending',  # Set status and handle it through business logic
            description=description
        )

        # Set transaction status to completed if all steps succeed
        transaction.status = 'completed'
        transaction.save()

        return transaction








