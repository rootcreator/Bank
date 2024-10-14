from django.conf import settings

from app.models import UserProfile


class StellarAnchorService:
    def __init__(self, gateways):
        if not isinstance(gateways, list):
            raise TypeError(f"Expected 'list', got {type(gateways)}")
        self.gateways = gateways  # List of available gateways
        print("Gateways initialized: ", self.gateways)

    def get_gateway_for_country(self, country):
        """Find a suitable gateway for the user's country"""
        for gateway in self.gateways:
            if gateway.supports_country(country):
                return gateway
        return None  # No suitable gateway found

    @staticmethod
    def check_user_balance(user):
        """Check the user's platform balance"""
        # Assuming you have a User model with a balance field
        return user.balance

    def initiate_deposit(self, user, amount):
        """Initiate deposit based on user country"""
        if amount <= 0:
            return {"error": "Deposit amount must be greater than zero."}

        # Fetch the user's country from their user profile
        country = user.userprofile.country

        # Get a suitable gateway for the user's country
        gateway = self.get_gateway_for_country(country)

        if gateway:
            account = settings.STELLAR_PLATFORM_PUBLIC_KEY
            return gateway.initiate_deposit(amount, account, country)
        else:
            return {
                "error": "No payment gateway available for your country.",
                "details": f"Supported gateways: {[g.__class__.__name__ for g in self.gateways]}"
            }

    def initiate_withdrawal(self, user, amount):
        """Initiate withdrawal based on user country"""
        if amount <= 0:
            return {"error": "Withdrawal amount must be greater than zero."}

        # Check user balance before proceeding with withdrawal
        user_balance = self.check_user_balance(user)
        if user_balance < amount:
            return {"error": "Insufficient balance for this withdrawal."}

        gateway = self.get_gateway_for_country(user.userprofile.country)
        if gateway:
            account = settings.STELLAR_PLATFORM_PUBLIC_KEY
            return gateway.initiate_withdrawal(amount, account)
        else:
            return {
                "error": "No payment gateway available for your country.",
                "details": f"Supported gateways: {[g.__class__.__name__ for g in self.gateways]}"
            }
