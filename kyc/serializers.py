from rest_framework import serializers
from app.models import UserProfile
from .models import KYCRequest


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'  # Adjust based on what fields you want to expose


class KYCRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCRequest
        fields = ['document_type', 'document_file', 'address_proof_file', 'selfie_file']
