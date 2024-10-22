from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UtilityView

# Create a router and register the viewset
router = DefaultRouter()
router.register(r'utility', UtilityView, basename='utility')

# Include the router-generated URLs in the urlpatterns
urlpatterns = [
    path('', include(router.urls)),
]
