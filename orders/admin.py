from django.contrib import admin
from .models import Customer, Service, Order, LaundryBusiness, UserProfile

admin.site.register(Customer)
admin.site.register(Service)

class OrderAdmin(admin.ModelAdmin):
    list_display =('id', 'customer', 'service', 'quantity', 'status', 'order_date')
    list_filter = ('status', 'order_date')

admin.site.register(Order, OrderAdmin)

@admin.register(LaundryBusiness)
class LaundryBusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner_name', 'is_active')

# --- ADD THIS PART ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'business', 'role')