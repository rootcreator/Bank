from rest_framework import serializers
from .models import KYCRequest


class KYCRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCRequest
        fields = ['id_document', 'selfie', 'address_document']
