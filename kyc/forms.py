from django import forms
from .models import KYCRequest


class KYCForm(forms.ModelForm):
    class Meta:
        model = KYCRequest
        fields = ['full_name', 'date_of_birth', 'address']


