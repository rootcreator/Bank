from django.contrib import admin
from .models import KYCRequest, Notification


@admin.register(KYCRequest)
class KYCApplicationAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'id_document', 'status', 'created_at')
    list_filter = ('status', 'created_at')


@admin.register(Notification)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ('user', 'message')
