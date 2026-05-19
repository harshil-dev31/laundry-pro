from django.contrib import admin
from .models import (
    Customer, Service, Order, LaundryBusiness, UserProfile,
    ClothingItem, OrderItem, OrderItemService
)

admin.site.register(Customer)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'unit')
    list_filter = ('category',)
    search_fields = ('name',)

@admin.register(ClothingItem)
class ClothingItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


class OrderItemServiceInline(admin.TabularInline):
    model = OrderItemService
    extra = 0
    readonly_fields = ('created_at',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('subtotal', 'created_at')
    inlines = [OrderItemServiceInline]


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'status', 'payment_status', 'total_price', 'order_date')
    list_filter = ('status', 'payment_status', 'order_date', 'business')
    search_fields = ('customer__name', 'id')
    readonly_fields = ('total_price', 'order_date', 'customer_name_backup')
    inlines = [OrderItemInline]

admin.site.register(Order, OrderAdmin)

@admin.register(LaundryBusiness)
class LaundryBusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner_name', 'is_active')

# --- ADD THIS PART ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'business', 'role')