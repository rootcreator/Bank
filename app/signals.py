from django.db.models.signals import post_save
from django.dispatch import receiver

from kyc.models import KYCRequest
from .models import LinkedAccount
from .models import UserProfile


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


@receiver(post_save, sender=LinkedAccount)
def create_circle_account(sender, instance, created, **kwargs):
    # Only link if the account is newly created and bank_account_id is not set
    if created and not instance.bank_account_id:
        try:
            instance.link_account_to_circle()  # Call the method to link to Circle
        except Exception as e:
            # Log the error or handle it as needed
            print(f"Error linking to Circle: {e}")


@receiver(post_save, sender=LinkedAccount)
def link_account_to_circle(sender, instance, created, **kwargs):
    """
    After a LinkedAccount is saved, fetch and cross-match Circle ID.
    """
    if created:  # Only run for newly created instances
        try:
            circle_id = instance.fetch_and_cross_match_circle_id()
            if circle_id:
                instance.bank_account_id = circle_id
                instance.save()  # Save the updated bank_account_id back to the database
                print(f"Circle ID linked: {circle_id}")
            else:
                print("No matching Circle account found.")
        except Exception as e:
            print(f"Error linking to Circle: {e}")


