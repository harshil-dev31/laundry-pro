from .models import PlatformSettings

def global_settings(request):
    # Try to get the settings object (ID=1)
    try:
        settings_obj = PlatformSettings.objects.get(id=1)
    except PlatformSettings.DoesNotExist:
        settings_obj = None

    return {
        # This keeps your existing settings page working
        'platform_settings': settings_obj,
        
        # This makes the NEW Red Banner work
        # (It checks if settings exist, then grabs the maintenance_mode status)
        'maintenance_mode': settings_obj.maintenance_mode if settings_obj else False,
    }


# orders/context_processors.py
# orders/context_processors.py
from django.db.models import Q
from .models import LaundryBusiness

def branch_data(request):
    context = {'my_shops': [], 'current_business': None}
    
    if request.user.is_authenticated:
        # Check if they are an Owner or Admin
        if request.user.groups.filter(name='Laundry Owner').exists() or request.user.is_superuser:
            
            # 1. Get all their shops
            if request.user.is_superuser:
                context['my_shops'] = LaundryBusiness.objects.all()
            else:
                # 🔥 THE FIX: Check username, first_name, and full_name (case-insensitive)
                context['my_shops'] = LaundryBusiness.objects.filter(
                    Q(owner_name__iexact=request.user.username) | 
                    Q(owner_name__iexact=request.user.first_name) |
                    Q(owner_name__iexact=request.user.get_full_name())
                ).distinct()
            
            # 2. Get current active business
            if hasattr(request.user, 'userprofile'):
                context['current_business'] = getattr(request.user.userprofile, 'business', None)
                
    return context