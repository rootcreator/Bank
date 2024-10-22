from django.urls import path
from .views import create_portfolio, credit_portfolio, withdraw_from_portfolio

urlpatterns = [
    path('portfolio/create/', create_portfolio, name='create_portfolio'),
    path('portfolio/credit/', credit_portfolio, name='credit_portfolio'),
    path('portfolio/withdraw/', withdraw_from_portfolio, name='withdraw_from_portfolio'),
]
