from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi 

# Create the schema view using get_schema_view from drf-yasg
schema_view = get_schema_view(
    openapi.Info(
        title="My API",
        default_version='v1',
        description="API documentation for my Django app",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@myapi.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)



import app.urls
import kyc.urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(app.urls)),
    path('kyc/', include(kyc.urls)),
    path('auth/', include('knox.urls')),

  # Swagger and ReDoc UI endpoints
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
