from django.db import models
from app.models import UserProfile


class KYCRequest(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    id_document = models.FileField(upload_to='kyc_documents/')
    selfie = models.FileField(upload_to='kyc_documents/')
    address_document = models.FileField(upload_to='kyc_documents/')
    status = models.CharField(max_length=20,
                              choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"KYC for {self.user.username}"


class Notification(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
