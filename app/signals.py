from django.db.models.signals import post_save
from django.dispatch import receiver

from kyc.models import KYCRequest
from .models import UserProfile


@receiver(post_save, sender=UserProfile)
def create_or_update_kyc(sender, instance, created, **kwargs):
    user = instance.user

    # If the profile is newly created, create a new KYCApplication
    if created:
        KYCRequest.objects.create(
            user=user,
            full_name=user.get_full_name(),
            date_of_birth=instance.date_of_birth,
            address=instance.address,
            status='pending'
        )
    else:
        # If the profile is updated, update the KYCApplication accordingly
        kyc_app, _ = KYCRequest.objects.get_or_create(user=user)
        kyc_app.full_name = user.get_full_name()
        kyc_app.date_of_birth = instance.date_of_birth
        kyc_app.address = instance.address
        kyc_app.save()
