from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserProfile
from kyc.models import KYCRequest


@receiver(post_save, sender=UserProfile)
def create_kyc_request(sender, instance, created, **kwargs):
    # Check if a new UserProfile is created and KYC is completed
    if created and instance.is_kyc_completed:
        # Ensure the KYCRequest creation happens after user profile creation
        KYCRequest.objects.create(
            user=instance.user,  # Assuming user is a ForeignKey in UserProfile
            full_name=instance.user.get_full_name(),  # Assuming User model has this method
            date_of_birth=instance.date_of_birth,
            address=instance.address,
            country=instance.country,
            id_document=instance.id_document,
            selfie=instance.selfie,
            address_document=instance.address_document,
            status='pending'  # Default status as 'pending'
        )
