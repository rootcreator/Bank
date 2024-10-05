from django.contrib import admin
from django.urls import path, include

import app.urls
import kyc.urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(app.urls)),
    path('kyc/', include(kyc.urls)),
    path('auth/', include('knox.urls')),
]
