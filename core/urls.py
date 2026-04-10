"""
URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include
from orders import views as order_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('orders/', include('orders.urls')),
    
    # 🔥 THE FIX: Intercept the login URL and point it to your new smart view!
    path('accounts/login/', order_views.CustomLoginView.as_view(), name='login'),
    
    # The rest of the default auth URLs (logout, password reset, etc)
    path('accounts/', include('django.contrib.auth.urls')),
    
    path('', order_views.public_home, name='public_home'),
]