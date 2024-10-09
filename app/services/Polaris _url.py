from django.urls import path
from .views import transaction_webhook

urlpatterns = [
    path('webhook/transaction/', transaction_webhook, name='transaction_webhook'),
]