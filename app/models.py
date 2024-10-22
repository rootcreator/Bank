import random
import uuid

from django.core.validators import RegexValidator
from django_countries.fields import CountryField
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.db import models, transaction
import logging

from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)
TRANSACTION_TYPES = (
    ('deposit', 'Deposit'),
    ('withdrawal', 'Withdrawal'),
    ('transfer', 'Transfer'),
    ('top-up', 'Top-up'),
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
    city = models.CharField(max_length=30)
    state = models.CharField(max_length=30)
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
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_id = models.CharField(max_length=6, unique=True, editable=False)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Store in USD
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generate_unique_account_id():
        while True:
            # Generate a random 6-digit number
            account_id = str(random.randint(100000, 999999))
            # Check if it is unique
            if not USDAccount.objects.filter(account_id=account_id).exists():
                return account_id

    def save(self, *args, **kwargs):
        # Generate account_id only if it's not already set (i.e., on creation)
        if not self.account_id:
            self.account_id = self.generate_unique_account_id()
        super().save(*args, **kwargs)

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
        if self.balance >= amount:
            self.balance -= amount
            self.save()
        else:
            raise ValidationError("Insufficient funds")

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
    payment_method = models.CharField(max_length=255)
    gateway = models.CharField(max_length=255)
    memo = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    source_account = models.CharField(max_length=255)
    destination_account = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    geolocation = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.status}"


def generate_unique_id():
    return str(uuid.uuid4())[:6]


class PlatformAccount(models.Model):
    name = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    unique_id = models.CharField(max_length=6, default=generate_unique_id, editable=False, unique=True)

    def __str__(self):
        return self.name  # No parentheses

    def deposit(self, amount):
        """Deposit funds to the platform account"""
        if amount <= 0:
            raise ValidationError("Deposit amount must be positive")
        self.balance += amount
        self.save()

    def withdraw(self, amount):
        """Withdraw funds from the platform account"""
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValidationError("Insufficient funds in platform account")
        self.balance -= amount
        self.save()


class LinkedAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bank_account_id = models.CharField(max_length=255)
    account_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\d+$', message="Account number must be numeric.")]
    )
    routing_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\d+$', message="Account number must be numeric.")]
    )
    bank_name = models.CharField(max_length=255)

    # Billing address fields
    billing_name = models.CharField(max_length=255)
    billing_city = models.CharField(max_length=255)
    billing_country = models.CharField(max_length=2)  # Use ISO 3166-1 alpha-2 format
    billing_line1 = models.CharField(max_length=255)
    billing_district = models.CharField(max_length=255)
    billing_postal_code = models.CharField(max_length=20)

    # Bank address fields
    bank_address_line1 = models.CharField(max_length=255)
    bank_address_city = models.CharField(max_length=255)
    bank_address_country = models.CharField(max_length=2)  # Use ISO 3166-1 alpha-2 format
    bank_address_district = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.bank_name} linked to {self.user.username}"


class Beneficiary(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    account_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\d+$', message="Account number must be numeric.")]
    )  # Optional
    routing_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\d+$', message="Account number must be numeric.")]
    )  # Optional
    bank_name = models.CharField(max_length=255, blank=True, null=True)  # Optional

    # Billing address fields
    billing_name = models.CharField(max_length=255)
    billing_city = models.CharField(max_length=255)
    billing_country = models.CharField(max_length=2)  # Use ISO 3166-1 alpha-2 format
    billing_line1 = models.CharField(max_length=255)
    billing_district = models.CharField(max_length=255)
    billing_postal_code = models.CharField(max_length=20)

    # Bank address fields
    bank_address_line1 = models.CharField(max_length=255)
    bank_address_city = models.CharField(max_length=255)
    bank_address_country = models.CharField(max_length=2)  # Use ISO 3166-1 alpha-2 format
    bank_address_district = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} (Beneficiary for {self.user.username})"


class Alert(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    flags = models.JSONField()
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert for {self.transaction} with flags {self.flags}"
        