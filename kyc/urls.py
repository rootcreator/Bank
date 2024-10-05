from django.urls import path
from kyc import views

urlpatterns = [
    path('submit_kyc/', views.submit_kyc, name='submit_kyc'),
]
