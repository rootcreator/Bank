from app.models import Fee


def calculate_fee(transaction_type, amount):
    total_amount, fee_amount = Fee.apply_transaction_fee(transaction_type, amount)
    net_amount = amount - fee_amount
    return total_amount, fee_amount, net_amount


def has_sufficient_balance(account, amount):
    return account.balance >= amount
