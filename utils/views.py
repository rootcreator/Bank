import requests
from requests import Response
from rest_framework import viewsets

from app.models import Transaction, USDAccount
from app.serializers import TransactionSerializer
from utils.services import ReloadlyService


class UtilityView(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

    def create(self, request, *args, **kwargs):
        amount = request.data.get('amount')
        currency = request.data.get('currency', 'USD')  # Default to USD if not provided
        recipient = request.data.get('recipient')
        user = request.user  # Assuming user is authenticated

        reloadly_service = ReloadlyService()

        try:
            # Step 1: Convert the amount from the chosen currency to USD
            usd_amount = self.convert_to_usd(amount, currency)

            # Fetch user's virtual balance in USD
            virtual_balance = USDAccount.objects.get(user=user)
            if virtual_balance.balance < usd_amount:
                return Response({'error': 'Insufficient funds'}, status=400)

            # Step 2: Call Reloadly API for the top-up (in the original currency)
            response = reloadly_service.top_up(amount, recipient, currency=currency)

            # Step 3: Deduct the equivalent USD amount from the user's virtual balance
            virtual_balance.balance -= usd_amount
            virtual_balance.save()

            # Step 4: Record the transaction
            Transaction.objects.create(
                user=user,
                amount=usd_amount,  # The transaction amount in USD
                transaction_type='top-up',
                original_amount=amount,  # The original amount in the user's currency
                original_currency=currency  # The currency the user chose
            )

            return Response({'status': 'success', 'details': response}, status=201)

        except Exception as e:
            return Response({'error': str(e)}, status=400)

    def convert_to_usd(self, amount, currency):
        """
        Converts the user's currency to USD by fetching real-time exchange rates
        and adding a 5% markup.
        """
        if currency == 'USD':
            return amount  # No conversion needed if the currency is USD

        # Step 1: Fetch the conversion rate dynamically
        conversion_rate = self.get_conversion_rate(currency, 'USD')

        # Step 2: Add a 5% markup to the conversion rate
        conversion_rate_with_markup = conversion_rate * 1.05

        # Step 3: Return the equivalent amount in USD
        return amount * conversion_rate_with_markup

    def get_conversion_rate(self, from_currency, to_currency):
        """
        Fetches the conversion rate for the given currencies from an external API (e.g., Fixer.io).
        """
        api_key = 'your_api_key_here'  # Replace with your Fixer.io API key

        url = f"http://data.fixer.io/api/latest?access_key={api_key}&symbols={from_currency},{to_currency}"
        response = requests.get(url)

        if response.status_code != 200:
            raise Exception(f"Error fetching conversion rate: {response.status_code}")

        data = response.json()

        if 'error' in data:
            raise Exception(f"Error from API: {data['error']['info']}")

        # Fetch the rate from the API response
        rates = data.get('rates', {})
        from_rate = rates.get(from_currency)
        to_rate = rates.get(to_currency)

        if from_rate and to_rate:
            # Convert the from_currency to to_currency (usually from_currency to USD)
            conversion_rate = to_rate / from_rate
            return conversion_rate
        else:
            raise Exception(f"Could not find conversion rate for {from_currency} to {to_currency}")