from django.db import models
from app.models import UserProfile
from django_countries.fields import CountryField


class KYCRequest(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    country = CountryField(blank_label='(select country)', null=True, blank=True)
    id_document = models.FileField(upload_to='kyc_documents/')
    selfie = models.FileField(upload_to='kyc_documents/')
    address_document = models.FileField(upload_to='kyc_documents/')
    status = models.CharField(max_length=20,
                              choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"KYC for {self.user}"  # Corrected from user_profile to user


class Notification(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
