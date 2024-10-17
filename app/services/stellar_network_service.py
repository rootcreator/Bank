from stellar_sdk import TransactionBuilder, Network, Keypair, Server
from django.conf import settings


class StellarNetworkService:
    def __init__(self):
        self.network = Network.PUBLIC_NETWORK_PASSPHRASE
        self.server = Server("https://horizon-testnet.stellar.org")
        self.platform_keypair = Keypair.from_secret(settings.STELLAR_PLATFORM_SECRET)
        self.asset_code = "USDC"
        self.asset_issuer = settings.USDC_ISSUER_PUBLIC_KEY

    def send_payment(self, destination, amount):
        try:
            transaction = (
                TransactionBuilder(
                    source_account=self.server.load_account(self.platform_keypair.public_key),
                    network_passphrase=self.network,
                    base_fee=100
                )
                .append_payment_op(
                    destination=destination,
                    amount=str(amount)
                    )
                .set_timeout(30)
                .build()
            )

            transaction.sign(self.platform_keypair)
            response = self.server.submit_transaction(transaction)
            return response
        except Exception as e:
            return {'error': str(e)}
