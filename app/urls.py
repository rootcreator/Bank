from django.urls import path
from . import views
from .views import password_reset_request, password_reset_confirm, account_view, balance_view, \
    transaction_view, health_check, LoginView, logout_view, deposit_callback, withdrawal_webhook

urlpatterns = [
    path('register/', views.register_user, name='register_user'),

    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),

    path('password-reset/', password_reset_request, name='password_reset_request'),
    path('password-reset-confirm/<uidb64>/<token>/', password_reset_confirm, name='password_reset_confirm'),

    path('update-kyc/', views.update_kyc_status, name='update_kyc_status'),

    path('account/', account_view, name='account_view'),
    path('balance/', balance_view, name='balance_view'),
    path('transactions/', transaction_view, name='transaction_view'),

    path('deposit/', views.initiate_deposit, name='deposit'),
    path('webhook/deposit/', deposit_callback, name='deposit_callback'),
    path('withdraw/', views.initiate_withdrawal, name='withdraw'),
    path('webhook/withdrawal/', withdrawal_webhook, name='withdrawal_webhook'),
    path('transfer/', views.initiate_transfer, name='transfer'),
    #path('deposit_funds/', deposit_funds, name='deposit-funds'),



    path('health/', health_check, name='health_check'),

]
