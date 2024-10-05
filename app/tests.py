from django.test import TestCase
from .stellar import StellarAnchorService
from app.models import User


class StellarAnchorServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.service = StellarAnchorService('anchor_url')

    def test_initiate_deposit(self):
        response = self.service.initiate_deposit(self.user, 100)
        self.assertIn('error', response)  # Adjust based on expected behavior

    def test_initiate_withdrawal(self):
        response = self.service.initiate_withdrawal(self.user, 50)
        self.assertIn('error', response)  # Adjust based on expected behavior

    def test_send_payment(self):
        response = self.service.send_payment('destination_public_key', 20)
        self.assertNotIn('error', response)  # Ensure successful payment

    # Add more tests for other methods...
