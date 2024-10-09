INSTALLED_APPS += ['polaris']

# Polaris asset configuration
POLARIS_ASSETS = [
    {
        'code': 'USDC',
        'issuer': 'YOUR_ASSET_ISSUER_PUBLIC_KEY',
        'distribution_account': 'YOUR_DISTRIBUTION_ACCOUNT_PUBLIC_KEY',
    }
]

# Polaris integration for custom KYC and transaction flows
POLARIS_INTEGRATIONS = {
    'kyc': 'app.services.kyc.CustomKYCIntegration',  # Your custom KYC integration
    'deposit': 'app.services.polaris.CustomDepositIntegration',  # Custom deposit logic
    'withdraw': 'app.services.polaris.CustomWithdrawIntegration'  # Custom withdrawal logic
}