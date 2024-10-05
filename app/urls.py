from django.urls import path
from . import views
from .views import password_reset_request, password_reset_confirm, account_view, balance_view, \
    transaction_view
from knox import views as knox_views
from .views import LoginView

urlpatterns = [
    path('register/', views.register_user, name='register_user'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate'),

    path('login/', LoginView.as_view(), name='login'),
    path('logout/', knox_views.LogoutView.as_view(), name='logout'),
    path('logout-all/', knox_views.LogoutAllView.as_view(), name='logoutall'),

    path('password-reset/', password_reset_request, name='password_reset_request'),
    path('password-reset-confirm/<uidb64>/<token>/', password_reset_confirm, name='password_reset_confirm'),

    path('update-kyc/', views.update_kyc_status, name='update_kyc_status'),

    path('account/', account_view, name='account_view'),
    path('balance/', balance_view, name='balance_view'),
    path('transactions/', transaction_view, name='transaction_view'),

    path('deposit/', views.initiate_deposit, name='deposit'),
    path('withdraw/', views.initiate_withdrawal, name='withdraw'),
    path('transfer/', views.initiate_transfer, name='transfer'),
    path('transaction/status/<str:transaction_id>/', views.transaction_status, name='transaction_status'),
    path('webhook/<str:provider>/', views.payment_webhook, name='payment_webhook'),


]
