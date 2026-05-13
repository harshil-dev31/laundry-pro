from django.shortcuts import render, redirect, get_object_or_404
from .models import Order, LaundryBusiness, Customer, Service, UserProfile, Task, StockRequest, PlatformSettings, Complaint, Shift
from .forms import OrderForm, RoleForm, CustomerForm, StaffCreationForm, LaundryBusinessForm, ServiceForm, StaffCreationForm, TaskForm, StockRequestForm, PlatformSettingsForm, ComplaintForm, ShiftForm, CustomerRegistrationForm,CustomerOrderForm, ReviewForm, StaffEditForm
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
import json
from django.db.models import Count, Sum, Q, Avg
from django.db.models.functions import ExtractMonth
from django.contrib.auth.models import User, Group
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django import forms  
import time
from django.contrib.auth.views import LoginView
import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.conf import settings
import re
from .email_utils import send_branch_credentials_email


def is_manager(user):
    return user.groups.filter(name__in=['Branch Manager', 'Laundry Owner']).exists() or user.is_superuser


@login_required
@user_passes_test(lambda u: u.is_superuser)
def super_admin_dashboard(request):
    businesses = LaundryBusiness.objects.all()
    context = {
        'businesses':businesses
    }
    return render(request, 'orders/super_admin_dashboard.html', context)
def admin_dashboard(request):
    # 1. Calculate Revenue Manually (Python Loop)
    all_orders = Order.objects.all()
    total_revenue = 0
    
    for order in all_orders:
        if order.service and order.service.price:
            total_revenue += order.service.price * order.quantity

    # 2. Other Counts
    total_orders = all_orders.count()
    total_businesses = LaundryBusiness.objects.count()
    total_users = User.objects.count()

    # 3. Get Recent Activity
    recent_orders = Order.objects.order_by('-order_date')[:5]  # <-- Added [:5] to limit to 5
    recent_users = User.objects.order_by('-date_joined')[:5]   # <-- Added [:5] to limit to 5

    return render(request, 'orders/admin_dashboard.html', {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_businesses': total_businesses,
        'total_users': total_users,
        'recent_orders': recent_orders,
        'recent_users': recent_users,
    })


def maintenance_control(request):
    # Placeholder: Redirects back to settings page for now
    return redirect('system_settings')

def system_settings(request):
    # Get the settings object (create one if it doesn't exist)
    settings_obj, created = PlatformSettings.objects.get_or_create(id=1)

    if request.method == 'POST':
        form = PlatformSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            return redirect('system_settings')
    else:
        form = PlatformSettingsForm(instance=settings_obj)

    return render(request, 'orders/system_settings.html', {'form': form})

def add_business(request):
    is_owner = request.user.groups.filter(name='Laundry Owner').exists()
    
    if not request.user.is_superuser and not is_owner:
        messages.error(request, "Access Denied. Only Owners can add branches.")
        return redirect('order_list')
        
    if request.method == 'POST':
        form = LaundryBusinessForm(request.POST, user=request.user)
        if form.is_valid():
            business = form.save(commit=False)
            
            # If an existing owner is creating a sub-branch, auto-fill their name
            if not request.user.is_superuser:
                business.owner_name = request.user.get_full_name() or request.user.username
                
            business.save() 
            
            # 🔥 AUTOMATIC ACCOUNT CREATION
            if request.user.is_superuser:
                o_name = business.owner_name or "owner"
                o_email = business.contact_email or ""
                o_phone = business.contact_phone or "0000"
                
                clean_name = o_name.replace(" ", "").lower()
                username = f"{clean_name}{o_phone[-4:]}" if len(o_phone) >= 4 else f"{clean_name}1234"
                raw_password = f"Owner@{o_phone}" if o_phone else "Welcome@123"
                
                existing_user = User.objects.filter(username=username).first()
                
                if not existing_user:
                    # SCENARIO A: Brand new owner
                    new_user = User.objects.create_user(
                        username=username,
                        email=o_email,
                        password=raw_password,
                        first_name=o_name
                    )
                    
                    # Add them to the 'Laundry Owner' group
                    owner_group, created = Group.objects.get_or_create(name='Laundry Owner')
                    new_user.groups.add(owner_group)
                    
                    # Create their Profile (Using the correct 'owner' role from your choices)
                    UserProfile.objects.create(
                        user=new_user,
                        business=business,
                        role='owner' 
                    )
                    
                    email_configured = bool(
                        getattr(settings, 'EMAIL_HOST_USER', None) and
                        getattr(settings, 'EMAIL_HOST_PASSWORD', None) and
                        settings.EMAIL_BACKEND != 'django.core.mail.backends.console.EmailBackend'
                    )

                    if email_configured and o_email:
                        email_sent, email_error = send_branch_credentials_email(
                            owner_name=o_name,
                            owner_email=o_email,
                            username=username,
                            password=raw_password,
                            branch_name=business.name
                        )
                        if email_sent:
                            messages.success(request, f"Branch '{business.name}' created! 🎉 Login credentials emailed to {o_email}")
                        else:
                            messages.warning(request, (
                                f"Branch '{business.name}' created, but email could not be sent. "
                                f"Reason: {email_error}. Username: {username} | Password: {raw_password}"
                            ))
                    else:
                        messages.warning(request, (
                            f"Branch '{business.name}' created, but email is not configured or the owner's email is unavailable. "
                            f"Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in your deployment environment to send credentials by email."
                        ))
                else:
                    # SCENARIO B: Existing owner
                    # Since the owner already exists, your Branch Switcher will automatically 
                    # pick up this new branch based on the 'owner_name' field!
                    messages.success(request, f"New Branch '{business.name}' created and added to existing owner '{username}'! 🎉")
            
            else:
                messages.success(request, f"New Branch '{business.name}' created!")
                
            if request.user.is_superuser:
                return redirect('super_admin_dashboard') 
            else:
                return redirect('manage_branches') 
    else:
        form = LaundryBusinessForm(user=request.user)
        
    return render(request, 'orders/business_form.html', {'form':form})
def toggle_business_status(request, business_id):
    business = get_object_or_404(LaundryBusiness, id=business_id)
    business.is_active = not business.is_active
    business.save()
    return redirect('super_admin_dashboard')

def edit_business(request, business_id):
    business = get_object_or_404(LaundryBusiness, id=business_id)

    if request.method == 'POST':
        form = LaundryBusinessForm(request.POST, instance=business)
        if form.is_valid():
            old_email = business.contact_email
            old_owner_name = business.owner_name
            updated_business = form.save()

            # Sync the linked owner user email and name when the branch owner details change.
            if old_email != updated_business.contact_email or old_owner_name != updated_business.owner_name:
                owner_profiles = UserProfile.objects.filter(business=updated_business, role='owner')
                for profile in owner_profiles:
                    user = profile.user
                    if old_email != updated_business.contact_email:
                        user.email = updated_business.contact_email
                    if old_owner_name != updated_business.owner_name:
                        user.first_name = updated_business.owner_name
                    user.save()

            return redirect('super_admin_dashboard')
    else:
        form = LaundryBusinessForm(instance=business)

    return render(request, 'orders/business_form.html', {'form': form})

@login_required
def manage_roles(request):
    # Security: Only Superuser can manage roles
    if not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('order_list')

    roles = Group.objects.all()
    return render(request, 'orders/role_list.html', {'roles': roles})

# 2. ADD or EDIT ROLE
@login_required
def edit_role(request, role_id=None):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('order_list')

    # If role_id is present, we are Editing. If None, we are Adding.
    if role_id:
        role = get_object_or_404(Group, id=role_id)
        action = "Edit"
    else:
        role = None
        action = "Add New"

    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            messages.success(request, f"Role '{form.cleaned_data['name']}' saved successfully!")
            return redirect('manage_roles')
    else:
        form = RoleForm(instance=role)

    return render(request, 'orders/role_form.html', {'form': form, 'action': action})

# 3. DELETE ROLE
@login_required
def delete_role(request, role_id):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('order_list')

    role = get_object_or_404(Group, id=role_id)
    role.delete()
    messages.success(request, "Role deleted successfully.")
    return redirect('manage_roles')
@login_required
# @permission_required('orders.view_order', raise_exception=True)
def order_list(request):

# 👇👇👇 START DETECTIVE MODE (This finds ALL data, hidden or not) 👇👇👇
    # print("\n🕵️‍♂️ DETECTIVE MODE: SEARCHING ENTIRE DATABASE...")
    # all_orders = Order.objects.all().order_by('-id')
    
    # found_missing = False
    # if all_orders.exists():
    #     for o in all_orders:
    #         # Get details
    #         c_name = o.customer.name if o.customer else "Unknown"
    #         c_user = o.customer.user.username if (o.customer and o.customer.user) else "NO USER"
    #         biz_name = o.business.name if o.business else "❌ ORPHAN (No Shop)"
            
    #         # Print details
    #         print(f"📦 Order #{o.id} | Customer: {c_name} (User: {c_user}) | Shop: {biz_name} | Status: {o.status}")
            
    #         if not o.business:
    #             found_missing = True
    # else:
    #     print("❌ DATABASE IS EMPTY!")
    # print("🕵️‍♂️ SEARCH COMPLETE\n")
    # 👆👆👆 END DETECTIVE MODE 👆👆👆
    # orphans = Order.objects.filter(business__isnull=True)
    
    # if orphans.exists():
    #     print(f"\n🚑 ATTEMPTING TO FIX {orphans.count()} ORPHAN ORDERS...")
    #     for orphan in orphans:
    #         # Case A: If Customer has a shop, give order to that shop
    #         if orphan.customer and orphan.customer.business:
    #             orphan.business = orphan.customer.business
    #             orphan.save()
    #             print(f"✅ FIXED: Order #{orphan.id} -> Assigned to {orphan.customer.business.name}")
            
    #         # Case B: If Service has a shop, give order to that shop
    #         elif orphan.service and orphan.service.business:
    #             orphan.business = orphan.service.business
    #             orphan.save()
    #             print(f"✅ FIXED: Order #{orphan.id} -> Assigned to {orphan.service.business.name}")
                
    #         else:
    #             print(f"❌ COULD NOT FIX: Order #{orphan.id} (No link found)")

    # print("\n🔍🔍🔍 SYSTEM CHECK: WHO OWNS THE ORDERS? 🔍🔍🔍")
    # # We fetch the last 10 orders from the WHOLE database to see what is going on
    # recent_orders = Order.objects.all().order_by('-id')[:10] 
    # for o in recent_orders:
    #     shop_name = o.business.name if o.business else "❌ ORPHAN (No Shop)"
    #     print(f"Order #{o.id} | Customer: {o.customer} | Assigned To: {shop_name} | Status: {o.status}")
    # print("🔍🔍🔍 END CHECK 🔍🔍🔍\n")
    # 👆👆👆 END SPY CODE 👆👆👆
    # --- UPDATE START: Redirect Customers safely ---
    # 1. Get the User Profile
    user_profile = getattr(request.user, 'userprofile', None)

    # 2. Check if they are a Customer (using the Profile we just fixed OR the Customer table)
    # If they are a customer, send them to the Rate Card immediately.
    if (user_profile and str(user_profile.role).strip().lower() == 'customer') or hasattr(request.user, 'customer'):
        return redirect('customer_dashboard') 
    # --- UPDATE END ---

    business_name = ''
    logged_in_user_role = ''
    if user_profile:
        business_name = user_profile.business.name if user_profile.business else ''
        logged_in_user_role = str(user_profile.role or '').strip()

    # 3. Check Business Profile
    if not user_profile or not user_profile.business:
        return render(request, 'orders/order_list.html', {
            'orders': [],
            'business_name': business_name,
            'logged_in_user_role': logged_in_user_role,
            'current_year': timezone.now().year,
            'monthly_revenue_json': json.dumps([0] * 12),
        })
    
    my_business = user_profile.business
    user = request.user

    # 4. Base Query (Get everything for this business)
    orders = Order.objects.filter(business=my_business).order_by('-order_date')

    current_year = timezone.now().year
    delivered_monthly_data = (
        Order.objects.filter(
            business=my_business,
            status__iexact='delivered',
            payment_status__iexact='Paid',
            order_date__year=current_year
        )
        .annotate(month=ExtractMonth('order_date'))
        .values('month')
        .annotate(revenue=Sum('total_price'))
        .order_by('month')
    )
    revenue_by_month = {item['month']: float(item['revenue'] or 0) for item in delivered_monthly_data}
    delivered_monthly_revenue = [revenue_by_month.get(month, 0) for month in range(1, 13)]

    # 5. SECURITY FILTER (Your Logic - CRITICAL)
    # Check if user is Manager or Owner
    is_manager = user.groups.filter(name__in=['Laundry Owner', 'Branch Manager']).exists()

    if not is_manager and not request.user.is_superuser:
        # If Staff: Show only orders created by them OR online orders (Customer group)
        orders = orders.filter(
            Q(created_by=user) | 
            Q(created_by__groups__name='Customer') |
            Q(created_by__isnull=True)   # <--- ADD THIS LINE (Fixes the Invisible Order)
        )

    # 6. CALCULATE DASHBOARD STATS (Based on the filtered list)
    total_orders = orders.count()
    
    # 🔥 THE FIX: Use __iexact to ignore uppercase/lowercase differences
    delivered_orders = orders.filter(status__iexact='delivered').count()
    
    # 🔥 SMARTER PENDING: Count everything that is NOT delivered and NOT cancelled
    pending_orders = orders.exclude(status__iexact='delivered').exclude(status__iexact='cancelled').count()

    # Revenue: Let's also make 'Paid' case-insensitive to prevent future bugs here!
    total_revenue = orders.filter(payment_status__iexact='paid').aggregate(Sum('total_price'))['total_price__sum'] or 0
    # 👇 NEW CODE: Fetch My Upcoming Shifts
    my_shifts = []
    
    if request.user.is_authenticated:
        from .models import Shift 
        
        today = timezone.now().date()
        
        # Fetch the next 4 upcoming shifts for the logged-in staff member
        my_shifts = Shift.objects.filter(
            staff=request.user, 
            date__gte=today
        ).order_by('date', 'start_time')[:4]
    # 👆 END NEW CODE
    return render(request, 'orders/order_list.html', {
        'orders': orders,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'delivered_orders': delivered_orders,
        'total_revenue': total_revenue,
        'is_manager': is_manager,
        'my_shifts': my_shifts,
        'current_year': current_year,
        'delivered_monthly_revenue_json': json.dumps(delivered_monthly_revenue),
        'business_name': business_name,
        'logged_in_user_role': logged_in_user_role,
    })
@login_required
def create_order(request, service_id=None):
    # 🛑 SECURITY LOCK: Check if they have permission to add orders
    if not request.user.has_perm('orders.add_order') and not request.user.is_superuser:
        messages.error(request, "Access Denied: You do not have permission to create new orders.")
        return redirect('order_list')
    # 1. Get the service object if the ID is provided in the URL
    service_obj = None
    if service_id:
        service_obj = get_object_or_404(Service, id=service_id)

    if request.method == 'POST':
        form = OrderForm(request.POST, request=request)
        
        # --- VALIDATION FILTER (Keep this, it prevents "Invalid Choice" errors) ---
        if hasattr(request.user, 'userprofile') and request.user.userprofile.business:
            form.fields['service'].queryset = Service.objects.filter(business=request.user.userprofile.business)
            # 👇 NEW: Filter customers for POST validation
            if 'customer' in form.fields:
                form.fields['customer'].queryset = Customer.objects.filter(business=request.user.userprofile.business).order_by('name')
                
        elif hasattr(request.user, 'customer') and hasattr(request.user.customer, 'business'):
             form.fields['service'].queryset = Service.objects.filter(business=request.user.customer.business)
             # 👇 NEW: Filter customers for POST validation
             if 'customer' in form.fields:
                 form.fields['customer'].queryset = Customer.objects.filter(business=request.user.customer.business).order_by('name')
        # -------------------------------------------------------------------------

        if form.is_valid():
            order = form.save(commit=False)

            # --- YOUR WORKING LOGIC STARTS HERE (DO NOT TOUCH) ---
            is_staff_or_manager = request.user.groups.filter(name__in=['Branch Manager', 'Staff', 'Laundry Owner']).exists() or request.user.is_superuser

            if is_staff_or_manager:
                if hasattr(request.user, 'userprofile') and request.user.userprofile.business:
                    order.business = request.user.userprofile.business
                else:
                    print("🛑 ERROR: Staff user has no Business assigned! Order will be an orphan.")
                    messages.error(request, "CRITICAL ERROR: Your account is not linked to any shop. Contact Admin.")
                    return render(request, 'orders/order_form.html', {'form': form, 'selected_service': service_obj})
            else:
                customer_obj, created = Customer.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'name': request.user.username,
                        'email': request.user.email,
                        'phone': '' 
                    }
                )
                order.customer = customer_obj
                
                # Priority Logic
                if service_obj and service_obj.business:
                    order.business = service_obj.business
                elif order.service and order.service.business:
                    order.business = order.service.business
                elif customer_obj.business:
                    order.business = customer_obj.business
                else:
                    print(f"⚠️ WARNING: Order #{order.id} will be an ORPHAN (No Business Linked)")

            order.status = 'Pending'
            order.save()
            
            messages.success(request, f"Order #{order.id} placed successfully!")
            return redirect('dashboard_redirect')
        
        else:
            print("\n🛑 FORM VALIDATION FAILED")
            print(form.errors)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
            
    else:
        # 2. GET REQUEST (Page Load)
        initial_data = {'service': service_obj} if service_obj else {}
        form = OrderForm(initial=initial_data, request=request)

    # --- 🔥 THE MISSING FIX FOR DISPLAY 🔥 ---
    # This logic runs when the page LOADS, filtering the dropdown before you see it.
    
    # 1. If Manager/Staff: Show only services and customers from THEIR Branch
    if hasattr(request.user, 'userprofile') and request.user.userprofile.business:
        form.fields['service'].queryset = Service.objects.filter(business=request.user.userprofile.business)
        # 👇 NEW: Filter customers for page load display
        if 'customer' in form.fields:
            form.fields['customer'].queryset = Customer.objects.filter(business=request.user.userprofile.business).order_by('name')
    
    # 2. If Customer: Show only services and customers from THEIR Assigned Branch
    elif hasattr(request.user, 'customer') and request.user.customer.business:
        form.fields['service'].queryset = Service.objects.filter(business=request.user.customer.business)
        # 👇 NEW: Filter customers for page load display
        if 'customer' in form.fields:
            form.fields['customer'].queryset = Customer.objects.filter(business=request.user.customer.business).order_by('name')
    # -----------------------------------------------------------------------

    context = {
        'form': form,
        'selected_service': service_obj
    }
    
    return render(request, 'orders/order_form.html', context)
@login_required
def create_customer(request):
    try:
        user_profile = request.user.userprofile
        my_business = user_profile.business
    except:
        messages.error(request, "Access Denied: You are not linked to a business.")
        return redirect('order_list')

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        
        if form.is_valid():
            customer = form.save(commit=False)
            customer.business = my_business
            customer.save()
            
            messages.success(request, f"Customer {customer.name} added!")
            return redirect('create_order')
        else:
            # THIS WILL PRINT THE ERROR IN YOUR BLACK TERMINAL SCREEN
            print("--------------------------------------------------")
            print("FORM FAILED. REASON:", form.errors) 
            print("--------------------------------------------------")
            messages.error(request, "Error: Please check the form details.")
            
    else:
        form = CustomerForm()

    # CHANGE THIS LINE TO MATCH YOUR FILE NAME:
    return render(request, 'orders/customer_form.html', {'form': form})
@login_required
def delete_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Security Check: Ensure the user owns this customer record
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile or user_profile.business != customer.business:
        messages.error(request, "You do not have permission to delete this customer.")
        return redirect('customer_list')
    
    # Delete the customer
    customer.delete()
    messages.success(request, "Customer deleted successfully. Their past orders are safe.")
    return redirect('customer_list')
@login_required
@permission_required('orders.view_customer', raise_exception=True)
def customer_list(request):
    # 1. Get the user's business
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile or not user_profile.business:
        return redirect('order_list') # Safety net
    
    # 2. Get all customers for THIS business
    customers = Customer.objects.filter(business=user_profile.business).order_by('-id')

    # 3. Search Logic
    search_query = request.GET.get('q')
    if search_query:
        customers = customers.filter(name__icontains=search_query) | customers.filter(phone_number__icontains=search_query)

    return render(request, 'orders/customer_list.html', {
        'customers': customers,
        'search_query': search_query
    })

@login_required
def edit_customer(request, customer_id):
    # 1. Get the customer (and ensure it belongs to the user's business for security)
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Security Check: Don't let them edit another shop's customer
    if customer.business != request.user.userprofile.business:
        return redirect('customer_list')

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'orders/customer_form.html', {'form': form, 'title': 'Edit Customer'})
@login_required
@permission_required('orders.change_order', raise_exception=True)
def edit_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # 1. Handle Form Submission
    if request.method == 'POST':
        # We pass 'request' so the form can filter services if needed
        form = OrderForm(request.POST, instance=order, request=request)

        # --- 🔥 FILTER LOGIC (Fixing the Dropdown Error) 🔥 ---
        if hasattr(request.user, 'userprofile') and request.user.userprofile.business:
            form.fields['service'].queryset = Service.objects.filter(business=request.user.userprofile.business)
        # ------------------------------------------------------
        
        # --- 🔥 DISABLE ONLY CUSTOMER, SERVICE, QUANTITY FOR READ-ONLY 🔥 ---
        fields_to_disable = ['customer', 'service', 'quantity']
        for field_name in fields_to_disable:
            if field_name in form.fields:
                form.fields[field_name].disabled = True
        # ---------------------------------------------------------------
        
        if form.is_valid():
            obj = form.save(commit=False)
            
            # --- 🔥 MANUALLY CAPTURE STATUS UPDATE 🔥 ---
            new_status = request.POST.get('status')
            if new_status:
                obj.status = new_status
            # ---------------------------------------------
            
            obj.save()
            messages.success(request, f"Order #{order.id} updated successfully!")
            return redirect('order_list')
    else:
        form = OrderForm(instance=order, request=request)
        
        # --- 🔥 FILTER LOGIC FOR DISPLAY (Fixing the Dropdown Error) 🔥 ---
        if hasattr(request.user, 'userprofile') and request.user.userprofile.business:
            form.fields['service'].queryset = Service.objects.filter(business=request.user.userprofile.business)
        # ------------------------------------------------------------------
        
        # --- 🔥 DISABLE ONLY CUSTOMER, SERVICE, QUANTITY FOR READ-ONLY 🔥 ---
        fields_to_disable = ['customer', 'service', 'quantity']
        for field_name in fields_to_disable:
            if field_name in form.fields:
                form.fields[field_name].disabled = True
        # ---------------------------------------------------------------
    
    # 2. Pass Variables to Template
    context = {
        'form': form,
        'page_title': f"Edit Order #{order.id}", # Fixes the wrong title
        'is_edit': True,                         # Tells HTML to show Status field
        'current_status': order.status           # Pre-selects the current status
    }

    return render(request, 'orders/order_form.html', context)

@login_required
@permission_required('orders.delete_order', raise_exception=True)
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == 'POST':
        order.delete()
        return redirect('order_list')

    return render(request, 'orders/order_confirm_delete.html', {'order': order})

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Laundry Owner').exists() or u.is_superuser)
def manage_services(request):
    user_profile = getattr(request.user, 'userprofile', None)

    if not user_profile or not user_profile.business:
        return render(request, 'orders/error_page.html', {'message': 'You are not Linked to a Laundry Business.'})
    my_business = user_profile.business

    if request.method == 'POST':
        # --- DELETE LOGIC ---
        if 'delete_service_id' in request.POST:
            service_id = request.POST.get('delete_service_id')
            service = get_object_or_404(Service, id=service_id)
            
            # Security: Ensure this service belongs to YOUR business before deleting
            if service.business == my_business:
                service.delete()
            return redirect('manage_services')

        # --- ADD/EDIT LOGIC ---
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.business = my_business
            
            selected_category = request.POST.get('category')
        if selected_category:
            service.category = selected_category

            # 2. Capture Unit (The New Fix)
            selected_unit = request.POST.get('unit')
            if selected_unit:
                service.unit = selected_unit
            # --- FORCE FIX END ---
            
            service.save()
            return redirect ('manage_services')

    else:
        form = ServiceForm()
    
    services = Service.objects.filter(business=my_business)
    context = {
        'services':services,
        'form':form,
        'business_name':my_business.name
    }
    return render (request, 'orders/manage_services.html', context)
@login_required
def edit_service(request, service_id):
    # 1. Get the specific service (and ensure it belongs to THIS business)
    service = get_object_or_404(Service, id=service_id, business=request.user.userprofile.business)
    
    if request.method == 'POST':
        # 2. Update fields with new data
        service.name = request.POST.get('name')
        service.price = request.POST.get('price')
        service.unit = request.POST.get('unit')
        service.category = request.POST.get('category')
        service.description = request.POST.get('description')
        
        # 3. Save
        service.save()
        messages.success(request, "Service updated successfully!")
        return redirect('manage_services')
    
    # If not POST, just redirect back
    return redirect('manage_services')
def manage_stock_requests(request):
    profile = getattr(request.user, 'userprofile', None)
    if not profile or not profile.business:
        return redirect('order_list')

    # Get requests for this business (Newest first)
    requests = StockRequest.objects.filter(business=profile.business).order_by('-created_at')

    return render(request, 'orders/manage_stock.html', {
        'requests': requests
    })
@require_POST
def update_stock_status(request, request_id):
    stock_req = get_object_or_404(StockRequest, id=request_id)
    
    # Security: Ensure Owner owns the shop that made the request
    if request.user.userprofile.business != stock_req.business:
        return redirect('manage_stock_requests') 

    # Check which button was clicked
    action = request.POST.get('action')
    if action == 'approve':
        stock_req.status = 'Approved'
    elif action == 'reject':
        stock_req.status = 'Rejected'
    
    stock_req.save()
    return redirect('manage_stock_requests')

@login_required
@permission_required('auth.add_user', raise_exception=True)
@user_passes_test(lambda u: u.groups.filter(name__in=['Laundry Owner', 'Branch Manager']).exists() or u.is_superuser)
def manage_staff(request):
    user_profile = getattr(request.user, 'userprofile', None)
    
    # 1. Check if the user has a business profile
    if not user_profile or not user_profile.business:
        return redirect('order_list')
        
    my_business = user_profile.business

    if request.method == 'POST':
        # --- DELETE USER LOGIC ---
        if 'delete_user_id' in request.POST:
            user_id_to_delete = request.POST.get('delete_user_id')
            user_to_delete = get_object_or_404(User, id=user_id_to_delete)
            
            user_profile_to_delete = getattr(user_to_delete, 'userprofile', None)
            
            # Ensure we only delete users from OUR business
            if user_profile_to_delete and user_profile_to_delete.business == my_business:
                is_target_manager = user_to_delete.groups.filter(name='Branch Manager').exists()
                is_requester_manager = request.user.groups.filter(name='Branch Manager').exists()

                # Safety: Managers cannot delete other Managers
                if is_requester_manager and is_target_manager:
                    messages.error(request, "Managers cannot remove other Managers.")
                else:
                    user_to_delete.delete()
                    messages.success(request, "Staff member removed successfully.")
            
            return redirect('manage_staff')

        # --- ADD STAFF LOGIC ---
        else:
            form = StaffCreationForm(request.POST, user=request.user)
            if form.is_valid():
                username = form.cleaned_data['username']
                password = form.cleaned_data['password']
                role_group = form.cleaned_data['role'] # Gets the Group Object
                email = form.cleaned_data['email']
                
                if User.objects.filter(username=username).exists():
                    messages.error(request, f"The username '{username}' is already taken.")
                elif User.objects.filter(email=email).exists():
                    messages.error(request, f"The email '{email}' is already in use by another account.")
                else:
                    # 1. Create User
                    new_user = User.objects.create_user(username=username, email=email, password=password)
                    
                    # 2. Add to Group (Permissions)
                    new_user.groups.add(role_group)
                    
                    # 3. Determine the 'Legacy' Role Name
                    # This is the FIX: Map "Branch Manager" -> "manager"
                    if role_group.name == 'Branch Manager':
                        profile_role = 'manager' 
                    else:
                        profile_role = role_group.name.lower()

                    # 4. Create Profile
                    UserProfile.objects.create(
                        user=new_user,
                        business=my_business, 
                        role=profile_role 
                    )
                    
                    messages.success(request, f"Staff member '{username}' added as {role_group.name}!")
                    return redirect('manage_staff')
            
    else:
        form = StaffCreationForm(user=request.user)

    # --- LIST STAFF LOGIC (THE FIX IS HERE) ---
    staff_profiles = UserProfile.objects.filter(business=my_business) \
                                        .exclude(role='Customer') \
                                        .exclude(role__icontains='owner') \
                                        .exclude(user=request.user)  # <--- THIS LINE HIDES YOU

    # Filter: If viewer is NOT an Owner (meaning they are a Manager), hide Owners from the list
    if not request.user.groups.filter(name='Laundry Owner').exists() and not request.user.is_superuser:
        staff_profiles = staff_profiles.exclude(role='owner').exclude(user__groups__name='Laundry Owner')

    return render(request, 'orders/manage_staff.html', {
        'form': form, 
        'staff_profiles': staff_profiles,
        'business_name': my_business.name
    })
def business_settings(request):
    # 1. Get the current user's business
    user_profile = getattr(request.user, 'userprofile', None)
    
    if not user_profile or not user_profile.business:
        # If they don't have a business linked, send them back to dashboard
        return redirect('order_list')
        
    my_business = user_profile.business

    # 2. Handle the Form
    if request.method == 'POST':
        form = LaundryBusinessForm(request.POST, instance=my_business)
        if form.is_valid():
            form.save()
            # Show a success message (optional) or just reload
            return redirect('business_settings')
    else:
        # Pre-fill the form with current details
        form = LaundryBusinessForm(instance=my_business)

    return render(request, 'orders/business_settings.html', {
        'form': form,
        'business': my_business
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name='Laundry Owner').exists() or u.is_superuser)
def my_branches(request):
    # --- 1. HANDLE THE DROPDOWN SWITCH (POST REQUEST) ---
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        if branch_id:
            target_business = get_object_or_404(LaundryBusiness, id=branch_id, is_active=True)            
            # 🔥 THE FIX: Smart Owner Validation
            valid_names = [
                request.user.username.lower(),
                request.user.first_name.lower(),
                request.user.get_full_name().lower()
            ]
            current_owner = target_business.owner_name.lower() if target_business.owner_name else ""
            
            # Security Check: Ensure this user actually owns this business!
            if current_owner not in valid_names and not request.user.is_superuser:
                messages.error(request, "You do not own this branch!")
                return redirect('order_list')

            # Update the UserProfile to point to this new business
            if hasattr(request.user, 'userprofile'):
                profile = request.user.userprofile
                profile.business = target_business
                profile.save()
                messages.success(request, f"Switched to {target_business.name} branch.")
                
            return redirect('order_list') # Redirect to dashboard after switching

    # --- 2. LOAD THE PAGE NORMALLY (GET REQUEST) ---
    # Find all businesses for the dropdown
    if request.user.is_superuser:
        # ONLY SHOW ACTIVE BRANCHES HERE
        my_shops = LaundryBusiness.objects.filter(is_active=True)
    else:
        # 🔥 THE FIX: Smart query for the GET request too!
        # ONLY SHOW ACTIVE BRANCHES HERE TOO
        my_shops = LaundryBusiness.objects.filter(
            Q(owner_name__iexact=request.user.username) | 
            Q(owner_name__iexact=request.user.first_name) |
            Q(owner_name__iexact=request.user.get_full_name())
        ).filter(is_active=True).distinct()
    
    # Get the currently active shop (to highlight it in dropdown)
    current_business = None
    if hasattr(request.user, 'userprofile'):
        current_business = getattr(request.user.userprofile, 'business', None)

    return render(request, 'orders/my_branches.html', {
        'my_shops': my_shops,
        'current_business': current_business
    })

@login_required
def switch_business(request, business_id):
    # 1. Find the target business
    target_business = get_object_or_404(LaundryBusiness, id=business_id, is_active=True)    
    # 🔥 THE FIX: Smart Owner Validation
    valid_names = [
        request.user.username.lower(),
        request.user.first_name.lower(),
        request.user.get_full_name().lower()
    ]
    current_owner = target_business.owner_name.lower() if target_business.owner_name else ""
    
    # 2. Security Check: Ensure this user actually owns this business!
    if current_owner not in valid_names and not request.user.is_superuser:
        return render(request, 'orders/error_page.html', {'message': "You do not own this branch!"})

    # 3. Update the UserProfile to point to this new business
    profile = request.user.userprofile
    profile.business = target_business
    profile.save()
    
    # 4. Go back to the Dashboard (It will now show the new shop's data!)
    return redirect('order_list')
# ✅ THE FIXED CODE
# @login_required
# def dashboard_redirect(request):
#     # Send the Super Admin straight to the normal shop dashboard!
#     if request.user.is_superuser:
#         return redirect('super_admin_dashboard')  # <-- Change this destination!
        
#     elif request.user.groups.filter(name='Laundry Owner').exists():
#         return redirect('admin_dashboard')
        
#     elif request.user.groups.filter(name='Staff').exists():
#         return redirect('staff_dashboard')
        
#     else:
#         return redirect('customer_dashboard')

def business_suspended(request):
    return render(request, 'orders/suspended.html')

@login_required
def task_list(request):
    profile = getattr(request.user, 'userprofile', None)
    if not profile or not profile.business:
        return redirect('order_list') # Safety check

    my_business = profile.business
    
    # 1. HANDLE ADDING A TASK (Only Managers/Owners)
    if request.method == 'POST' and 'add_task' in request.POST:
        form = TaskForm(request.POST, business=my_business)
        if form.is_valid():
            task = form.save(commit=False)
            task.business = my_business
            task.save()
            return redirect('task_list')
    else:
        form = TaskForm(business=my_business)

    # 2. GET TASKS
    # Show tasks that belong to this business
    tasks = Task.objects.filter(business=my_business).order_by('-created_at')

    return render(request, 'orders/task_list.html', {
        'tasks': tasks,
        'form': form,
        'is_manager': request.user.groups.filter(name__in=['Laundry Owner', 'Branch Manager']).exists()
    })


@login_required
def complete_task(request, task_id):
    # 1. Find the task
    task = get_object_or_404(Task, id=task_id)
    
    # 2. Security Check: ensure user belongs to the same business
    user_profile = getattr(request.user, 'userprofile', None)
    if user_profile and user_profile.business == task.business:
        
        # 3. Mark it as done
        task.is_completed = True
        task.save()
        
    return redirect('task_list')

@login_required
def stock_request_lists(request):
    profile = getattr(request.user, 'userprofile', None)
    if not profile or not profile.business:
        return redirect('order_list')

    if request.method == 'POST':
        form = StockRequestForm(request.POST)
        if form.is_valid():
            stock = form.save(commit=False)
            stock.business = profile.business
            stock.requested_by = request.user
            stock.save()
            return redirect('stock_request_list')
    else:
        form = StockRequestForm()
        stock_requests = StockRequest.objects.filter(business=profile.business).order_by('created_at')
        is_manager = request.user.groups.filter(name='Branch Manager').exists()
        return render(request, 'orders/stock_request.html',{
            'stock_requests': stock_requests,
            'form':form,
            'is_manager': is_manager

        })

@login_required
def complaint_list(request):
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile or not user_profile.business:
        messages.error(request, "Access Denied")
        return redirect('order_list')
    
    my_business = user_profile.business

    # 1. Fetch Customers & Orders directly (for the manual dropdowns)
    my_customers = Customer.objects.filter(business=my_business)
    my_orders = Order.objects.filter(business=my_business).order_by('-id')

    if request.method == 'POST':
        form = ComplaintForm(request.POST, user=request.user)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.business = my_business
            complaint.save()
            complaint.status = 'Pending'
            messages.success(request, "Complaint logged successfully.")
            return redirect('complaint_list')
        else:
            print("Form Errors:", form.errors)
    else:
        form = ComplaintForm(user=request.user)

    complaints = Complaint.objects.filter(business=my_business).order_by('-created_at')

    return render(request, 'orders/complaint_list.html', {
        'complaints': complaints, 
        'form': form,
        # PASS THESE TWO LISTS 👇
        'all_customers': my_customers,
        'all_orders': my_orders,
        'is_manager': request.user.groups.filter(name__in=['Branch Manager', 'Laundry Owner']).exists()
    })
@login_required
def resolve_complaint(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    
    # Security: Ensure it belongs to my business
    if complaint.business != request.user.userprofile.business:
        return redirect('complaint_list')
    
    if request.method == 'POST':
        # 1. Get the note from the popup
        note = request.POST.get('resolution_note')
        
    complaint.status = 'Resolved'
    complaint.resolved_at = timezone.now()
    complaint.resolution_note = note
    complaint.save()
    
    messages.success(request, "Complaint marked as Resolved and reply sent to customer!.")
    return redirect('complaint_list')

@login_required
def schedule_list(request):
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile or not user_profile.business:
        return redirect('order_list')
    
    my_business = user_profile.business

    # 1. Handle "Add Shift"
    if request.method == 'POST':
        form = ShiftForm(request.POST, user=request.user)
        if form.is_valid():
            shift = form.save(commit=False)
            shift.business = my_business
            shift.save()
            messages.success(request, "Shift assigned successfully.")
            return redirect('schedule_list')
    else:
        form = ShiftForm(user=request.user)

    # 2. Get Shifts (Only show today onwards to keep list clean)
    today = datetime.date.today()
    shifts = Shift.objects.filter(business=my_business, date__gte=today).order_by('date', 'start_time')

    return render(request, 'orders/schedule_list.html', {
        'shifts': shifts,
        'form': form,
        'is_manager': request.user.groups.filter(name__in=['Branch Manager', 'Laundry Owner']).exists()
    })

@login_required
def delete_shift(request, shift_id):
    shift = get_object_or_404(Shift, id=shift_id)
    # Security Check
    if shift.business == request.user.userprofile.business:
        shift.delete()
        messages.success(request, "Shift removed.")
    return redirect('schedule_list')

@login_required
def branch_reports(request):
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile or not user_profile.business:
        return redirect('order_list')
    
    my_business = user_profile.business
    today = datetime.date.today()
    current_month = today.month

    # 1. Base Query
    all_orders = Order.objects.filter(business=my_business)

    # 2. Revenue (FIXED: changed 'created_at' to 'order_date')
    total_revenue = all_orders.filter(payment_status='Paid').aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    monthly_revenue = all_orders.filter(
        payment_status='Paid', 
        order_date__month=current_month  # <--- FIXED HERE
    ).aggregate(Sum('total_price'))['total_price__sum'] or 0

    # 3. Order Counts
    total_orders_count = all_orders.count()
    pending_orders_count = all_orders.exclude(status='delivered').count()
    completed_orders_count = all_orders.filter(status='delivered').count()

    # 4. Today's Stats (FIXED: changed 'created_at' to 'order_date')
    today_orders = all_orders.filter(order_date__date=today).count() # <--- FIXED HERE
    
    today_revenue = all_orders.filter(
        payment_status='Paid', 
        order_date__date=today  # <--- FIXED HERE
    ).aggregate(Sum('total_price'))['total_price__sum'] or 0

    return render(request, 'orders/branch_reports.html', {
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'today_revenue': today_revenue,
        'total_orders_count': total_orders_count,
        'pending_orders_count': pending_orders_count,
        'completed_orders_count': completed_orders_count,
        'today_orders': today_orders,
        'business_name': my_business.name
    })
@login_required
def order_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'orders/order_receipt.html', {'order': order})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
def fix_my_orders(request):
    # 1. Get my business
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile:
        return redirect('order_list')

    my_business = user_profile.business
    
    # 2. Get ALL orders for this business (Even if Jay created them!)
    all_shop_orders = Order.objects.filter(business=my_business)
    
    # 3. Force update ALL of them to belong to ME (Hari)
    count = all_shop_orders.count()
    all_shop_orders.update(created_by=request.user)
    
    messages.success(request, f"Success! Forcefully assigned {count} orders to {request.user.username}")
    return redirect('order_list')

# orders/views.py


@permission_required('orders.add_customer', raise_exception=True)
def customer_register(request):
    user_profile = getattr(request.user, 'userprofile', None)
    
    # 1. Determine Identity
    is_owner = False
    auto_assign_business = False
    my_business = None

    if user_profile and user_profile.business:
        if 'owner' in str(user_profile.role).lower():
            is_owner = True
        else:
            auto_assign_business = True
            my_business = user_profile.business

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        
        if auto_assign_business:
            form.fields['business'].required = False
        
        if form.is_valid():
            # ==========================================================
            # 🛑 SECURITY GATE - OTP CHECK 🛑
            # ==========================================================
            user_otp = str(request.POST.get('otp_code', '')).strip()
            session_otp = str(request.session.get('generated_otp', '')).strip()
            
            if session_otp and user_otp != session_otp:
                messages.error(request, "❌ Invalid Verification Code. You entered the wrong code.")
                return render(request, 'orders/customer_register.html', {'form': form})
            
            if 'generated_otp' in request.session: del request.session['generated_otp']
            # ==========================================================

            final_username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            # 🔥 CAPTURE EMAIL FROM FORM 🔥
            email_address = form.cleaned_data.get('email')
            
            try:
                # 1. Create Login User WITH EMAIL
                # ✅ This ensures the email is saved to the account properly
                new_user = User.objects.create_user(
                    username=final_username, 
                    email=email_address, 
                    password=password
                )                
                
                # 2. Save Customer Data
                customer = form.save(commit=False)
                customer.user = new_user
                if auto_assign_business:
                    customer.business = my_business
                customer.save()

                # 3. Create User Profile
                from .models import UserProfile 
                UserProfile.objects.update_or_create(
                    user=new_user,
                    defaults={
                        'business': customer.business,
                        'role': 'Customer'
                    }
                )

                # 4. Add to Django Group
                from django.contrib.auth.models import Group
                group, _ = Group.objects.get_or_create(name='Customer')
                new_user.groups.add(group)

                messages.success(request, f"Customer {final_username} registered successfully!")
                return redirect('order_list')

            except Exception as e:
                messages.error(request, f"Error: {e}")
                if 'new_user' in locals():
                    new_user.delete() 
                
    else:
        form = CustomerRegistrationForm()

    if is_owner:
        form.fields['business'].widget = forms.Select(attrs={'class': 'form-select'})
        form.fields['business'].queryset = LaundryBusiness.objects.all()
    elif auto_assign_business:
        form.fields['business'].widget = forms.HiddenInput()
        form.fields['business'].required = False

    return render(request, 'orders/customer_register.html', {'form': form})
@login_required
def customer_dashboard(request):
    # Security: Only kick them out if they are STAFF or OWNER (NOT a Customer)
    if hasattr(request.user, 'userprofile') and str(request.user.userprofile.role).strip().lower() != 'customer':
        return redirect('order_list')
        
    # Get the logged-in customer
    try:
        customer = request.user.customer
    except AttributeError:
        # If something is wrong (no customer profile linked), go to login
        return redirect('login')

    # --- FIX START: ROBUST STATUS CHECK ---
    # Define finished statuses so active orders only include orders still in progress.
    # Status values may be stored in lowercase or title case.
    active_orders = Order.objects.filter(customer=customer).exclude(status__iexact='delivered').exclude(status__iexact='cancelled').order_by('-order_date')

    # History should show delivered orders only.
    history_orders = Order.objects.filter(customer=customer, status__iexact='delivered').order_by('-order_date')[:5]
    # --- FIX END ---

    return render(request, 'orders/customer_dashboard.html', {
        'customer': customer,
        'active_orders': active_orders,
        'history_orders': history_orders
    })
@login_required
def dashboard_redirect(request):
    user = request.user
    
    # 1. Super Admin -> HQ
    if user.is_superuser:
        return redirect('super_admin_dashboard')

    # 2. Customer -> Customer Dashboard
    # Customer accounts may have both userprofile and customer rows.
    if (hasattr(user, 'customer')) or (
        hasattr(user, 'userprofile') and str(user.userprofile.role).strip().lower() == 'customer'
    ):
        return redirect('customer_dashboard')
        
    # 3. Staff/Manager/Owner -> Staff Dashboard
    # (They have a 'userprofile' linked to them)
    if hasattr(user, 'userprofile'):
        return redirect('order_list')
        
    # 4. Fallback (Just in case)
    return redirect('order_list')
# In forms.py

class CustomerOrderForm(forms.ModelForm):
    class Meta:
        model = Order
        # I added 'pickup_date' and 'pickup_time' to your existing list
        fields = ['service', 'quantity', 'pickup_date', 'pickup_time', 'notes']
        
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional instructions...'}),
            
            # --- NEW WIDGETS START ---
            'pickup_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pickup_time': forms.Select(attrs={'class': 'form-select'}),
            # --- NEW WIDGETS END ---
        }

    # I KEPT YOUR LOGIC HERE EXACTLY AS IT WAS
    def __init__(self, user, *args, **kwargs):
        super(CustomerOrderForm, self).__init__(*args, **kwargs)
        
        # This is your logic that ensures customers only see services from their branch
        if hasattr(user, 'customer') and user.customer.business:
            self.fields['service'].queryset = Service.objects.filter(business=user.customer.business)
        else:
            # Safety: If something is wrong with the customer account, show no services
            self.fields['service'].queryset = Service.objects.none()
@login_required
def customer_order_history(request):
    try:
        customer = request.user.customer
    except:
        return redirect('order_list')

    # Get all orders (newest first)
    my_orders = Order.objects.filter(customer=customer).order_by('-order_date')

    return render(request, 'orders/customer_history.html', {'orders': my_orders})

@login_required
def customer_raise_complaint(request):
    try:
        customer = request.user.customer
    except:
        return redirect('order_list')

    # 1. FETCH THE ORDERS MANUALLY (The "Manual Override")
    # We get them directly from the database to be 100% sure they exist
    user_orders = Order.objects.filter(customer=customer).order_by('-id')

    if request.method == 'POST':
        form = ComplaintForm(request.POST, user=request.user)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.customer = customer
            complaint.business = customer.business
            complaint.status = 'Pending'
            complaint.save()
            messages.success(request, "Complaint submitted successfully!")
            return redirect('customer_dashboard')
        else:
            messages.error(request, "Failed. Check details.")
    else:
        form = ComplaintForm(user=request.user)

    context = {
        'form': form,
        'user_orders': user_orders  # <--- PASSING THE LIST TO HTML
    }
    return render(request, 'orders/customer_complaint.html', context)
# In orders/views.py


# @login_required
# def customer_raise_complaint(request):
#     try:
#         # Check if the user is a customer
#         customer = request.user.customer
#     except:
#         return redirect('order_list')

#     if request.method == 'POST':
#         # 1. SEND USER WHEN SUBMITTING
#         form = ComplaintForm(request.POST, user=request.user)
        
#         if form.is_valid():
#             complaint = form.save(commit=False)
#             complaint.customer = customer
#             complaint.business = customer.business
#             complaint.status = 'Pending'
#             complaint.save()
#             messages.success(request, "Complaint submitted successfully!")
#             return redirect('customer_dashboard')
#         else:
#             print("!!! FORM ERROR:", form.errors)
#             messages.error(request, "Failed. Check details.")
#     else:
#         # 2. PASS USER HERE TOO
#         form = ComplaintForm(user=request.user)

#     return render(request, 'orders/customer_complaint.html', {'form': form})




@login_required
def accept_payment(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        
        # 1. Get the payment method from the pop-up form
        method = request.POST.get('payment_method')
        
        # 2. Update Status and Method
        order.payment_status = 'Paid'
        order.payment_method = method
        
        # 3. --- NEW FIX: SAVE THE STAFF MEMBER'S NAME ---
        # This grabs the currently logged-in user (Staff/Manager) and saves them
        order.payment_collected_by = request.user 
        # ------------------------------------------------
        
        order.save()
        
        messages.success(request, f"Payment of ₹{order.total_price} collected by {request.user.username}!")
        
    return redirect('dashboard_redirect')
@login_required
def customer_payment(request, order_id):
    # 1. Get the order securely (only if it belongs to this customer)
    try:
        customer = request.user.customer
        order = get_object_or_404(Order, id=order_id, customer=customer)
    except:
        messages.error(request, "Order not found or access denied.")
        return redirect('customer_dashboard')

    # 2. Check if already paid
    if order.payment_status == 'Paid':
        messages.info(request, "This order is already paid.")
        return redirect('customer_dashboard')

    if request.method == 'POST':
        # 3. Process the Mock Payment
        # (Here is where you would connect Stripe/Razorpay in a real app)
        
        order.payment_status = 'Paid'
        order.save()
        
        messages.success(request, f"Payment of ₹{order.total_price} successful! Thank you.")
        return redirect('customer_dashboard')

    # 4. Render the payment page
    return render(request, 'orders/customer_payment.html', {'order': order})
@login_required
def rate_service(request, order_id):
    customer = request.user.customer
    order = get_object_or_404(Order, id=order_id, customer=customer)

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your feedback!")
            return redirect('customer_dashboard')
        else:
            # THIS WILL PRINT THE ERROR IN YOUR TERMINAL 👇
            print("------------------------------------------------")
            print("RATING ERROR:", form.errors)
            print("------------------------------------------------")
            messages.error(request, "Error submitting review. Check details.")
            
    else:
        form = ReviewForm(instance=order)

    return render(request, 'orders/rate_service.html', {'form': form, 'order': order})
# orders/views.py

@login_required
def approve_order(request, order_id):
    # 1. Get the order
    order = get_object_or_404(Order, id=order_id)
    
    # 2. Security Check (Only Staff/Managers can approve)
    if not request.user.groups.filter(name__in=['Laundry Owner', 'Branch Manager', 'Staff']).exists() and not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('order_list')

    if request.method == 'POST':
        # 3. Get the Date from the form
        delivery_date = request.POST.get('delivery_date')
        
        if delivery_date:
            order.estimated_delivery = delivery_date
            order.is_approved = True
            order.status = 'Processing' # Move from 'Pending' to 'Processing'
            order.save()
            messages.success(request, f"Order #{order.id} approved! Delivery set for {delivery_date}.")
        else:
            messages.error(request, "Please select a delivery date.")
            
    return redirect('order_list')
@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # 1. Permission Check (Owner, Manager, Staff)
    allowed_roles = ['Laundry Owner', 'Branch Manager', 'Staff']
    if not request.user.groups.filter(name__in=allowed_roles).exists() and not request.user.is_superuser:
        messages.error(request, "Access Denied. You cannot update order status.")
        return redirect('order_list')

    if request.method == 'POST':
        # 2. Get Data from Modal
        new_status = request.POST.get('status')
        new_date = request.POST.get('new_date')
        
        # 3. Update Status
        if new_status:
            order.status = new_status
            
        # 4. Update Date (Only if they selected one)
        if new_date:
            order.estimated_delivery = new_date
            
        order.save()
        messages.success(request, f"Order #{order.id} updated to '{new_status}'")
        
    return redirect('order_list')
@login_required
def rate_card(request):
    # 1. Identify the Business (Profile vs Customer Table)
    user_profile = getattr(request.user, 'userprofile', None)
    my_business = None

    if user_profile and user_profile.business:
        my_business = user_profile.business
    elif hasattr(request.user, 'customer'):
        my_business = request.user.customer.business

    if not my_business:
        messages.error(request, "We couldn't find your branch details. Please contact support.")
        return redirect('login')

    # 2. Fetch ALL services for this shop
    services = Service.objects.filter(business=my_business).order_by('category')

    # 3. DEBUG: Print to terminal to see if services exist
    print(f"DEBUG: Found {services.count()} services for {my_business.name}")

    # 4. DYNAMIC GROUPING (The Fix)
    # We loop through results and build the dictionary automatically based on YOUR database values
    categories = {}
    for service in services:
        # Get the category name (e.g., 'Washing', 'Dry Cleaning')
        cat_name = service.category 
        
        # If this category isn't in our list yet, add it
        if cat_name not in categories:
            categories[cat_name] = []
        
        # Add the service to the list
        categories[cat_name].append(service)

    return render(request, 'orders/rate_card.html', {
        'categories': categories, # This is now a dictionary of { 'Category Name': [List of Services] }
        'business_name': my_business.name 
    })
@login_required
def customer_request_pickup(request):
    try:
        # Ensure the user is actually a customer
        customer = request.user.customer
    except:
        # If not a customer, send them away
        return redirect('order_list')

    if request.method == 'POST':
        # We pass 'request.user' so the form knows which branch to show
        form = CustomerOrderForm(request.user, request.POST)
        
        if form.is_valid():
            order = form.save(commit=False)
            
            # Auto-fill system fields
            order.customer = request.user.customer
            # Link order to the customer's branch
            if hasattr(request.user, 'customer') and request.user.customer.business:
                order.business = request.user.customer.business
            
            order.created_by = request.user
            order.status = 'Pending' # Default status
            order.payment_status = 'Unpaid'
            
            # simple price calculation (optional)
            if order.service and order.quantity:
                order.total_price = order.service.price * order.quantity
            
            order.save()
            return redirect('customer_dashboard')
    else:
        # GET request: Load empty form
        form = CustomerOrderForm(request.user)

    # Pass customer object to template
    customer = request.user.customer if hasattr(request.user, 'customer') else None
    return render(request, 'orders/customer_create_order.html', {
        'form': form,
        'customer': customer
    })

# In orders/views.py

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType

# 1. THE HUB: List all users so Admin can pick one
# In orders/views.py

@login_required
def admin_user_list(request):
    if not request.user.is_superuser:
        return redirect('dashboard_redirect')

    # --- CHANGED LINE BELOW ---
    # We use .filter(is_superuser=False) to HIDE the admin/owner account
    users = User.objects.filter(is_superuser=False).order_by('-date_joined')
    
    # We pre-calculate the branch name here to avoid errors in the HTML
    for u in users:
        u.branch_name = "-" # Default if they have no branch
        
        # 1. Check if they are Staff/Manager
        if hasattr(u, 'userprofile') and u.userprofile.business:
             u.branch_name = u.userprofile.business.name
             
        # 2. Check if they are a Customer
        elif hasattr(u, 'customer') and u.customer.business:
             u.branch_name = u.customer.business.name

    context = {'users': users}
    return render(request, 'orders/admin_user_list.html', context)

@login_required
def edit_user_permissions(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard_redirect')

    user_to_edit = get_object_or_404(User, id=user_id)
    
    # 1. DEFINE THE SPECIFIC PERMISSIONS YOU WANT TO SHOW
    # Format: 'codename': 'Friendly Label to Show'
    wanted_permissions = {
        'add_user': 'Can Hire New Staff',
        'add_customer': 'Can Register Customers',
        'add_order': 'Can Create New Orders',
        'change_order': 'Can Edit/Update Orders',
        'delete_order': 'Can Delete Orders (Careful!)',
    }

    # 2. Fetch only these permissions from the database
    permissions_obj_list = Permission.objects.filter(codename__in=wanted_permissions.keys())

    # 3. Check what the user already has (from their Role/Group)
    role_permissions = set()
    for group in user_to_edit.groups.all():
        role_permissions.update(group.permissions.all())

    if request.method == 'POST':
        selected_perms_ids = request.POST.getlist('permissions')
        
        # Clear OLD custom permissions
        user_to_edit.user_permissions.clear()
        
        # Add NEW custom permissions
        for perm_id in selected_perms_ids:
            perm = Permission.objects.get(id=perm_id)
            user_to_edit.user_permissions.add(perm)
            
        messages.success(request, f"Permissions updated for {user_to_edit.username}")
        return redirect('admin_user_list')

    # 4. Prepare the list for the HTML
    # We combine the Permission Object with your Friendly Label
    final_permission_list = []
    for perm in permissions_obj_list:
        final_permission_list.append({
            'object': perm,
            'label': wanted_permissions.get(perm.codename, perm.name), # Use your custom label
            'is_inherited': perm in role_permissions,
            'is_direct': perm in user_to_edit.user_permissions.all()
        })

    context = {
        'user_to_edit': user_to_edit,
        'final_permission_list': final_permission_list,
    }
    return render(request, 'orders/edit_user_permissions.html', context)

# In orders/views.py

@login_required
def delete_user(request, user_id):
    # Security: Only Super Admin can do this
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to delete users.")
        return redirect('dashboard_redirect')
        
    user_to_delete = get_object_or_404(User, id=user_id)
    
    # Safety: Prevent Admin from deleting themselves!
    if user_to_delete == request.user:
        messages.error(request, "You cannot delete your own account while logged in!")
    else:
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f"User '{username}' has been deleted successfully.")
        
    return redirect('admin_user_list')
# In orders/views.py
from .forms import CustomerForm # Ensure this is imported

@login_required
def customer_profile(request):
    customer = get_object_or_404(Customer, user=request.user)

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        new_email = request.POST.get('email', '').strip()

        if form.is_valid():
            # 1. Save Customer Data (Phone, Address, etc.)
            customer_obj = form.save(commit=False)
            customer_obj.email = new_email  # 🔥 Ensure it saves to Customer table
            customer_obj.save()
            
            # 2. Sync Email to the User Login Table
            if new_email and new_email != request.user.email:
                if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
                    messages.error(request, "This email is already used by another account.")
                else:
                    user = request.user
                    user.email = new_email
                    user.save()
                    messages.success(request, "Profile and Email updated successfully!")
            else:
                 messages.success(request, "Profile updated successfully!")
                 
            return redirect('customer_dashboard')
    else:
        # Load form with User's email as the default
        form = CustomerForm(instance=customer, initial={'email': request.user.email})
        
        # 🔥 THE RECOVERY FIX: 
        # If User table is blank, try to pull from the Customer table
        if not request.user.email:
            saved_email = getattr(customer, 'email', None)
            if saved_email:
                # This fills the local variable so the template shows it
                request.user.email = saved_email 
                
    return render(request, 'orders/customer_profile.html', {'form': form})
def public_register(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            # 🔥 FIX: DEFINE email_address FIRST 🔥
            email_address = form.cleaned_data.get('email')

            # ==========================================================
            # 🛑 SECURITY GATE - HARD STOP PROTOCOL 🛑
            # ==========================================================
            user_otp = str(request.POST.get('otp_code', '')).strip()
            session_otp = str(request.session.get('generated_otp', '')).strip()
            
            if not session_otp or session_otp == 'None':
                messages.error(request, "⚠️ Verification failed. Please click 'Verify' again.")
                return render(request, 'orders/register.html', {'form': form})

            if user_otp != session_otp:
                messages.error(request, "❌ Invalid Verification Code. You entered the wrong code.")
                return render(request, 'orders/register.html', {'form': form})
            
            if 'generated_otp' in request.session: del request.session['generated_otp']
            # ==========================================================

            final_username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            try:
                print("\n=== DEBUGGING START ===")
                # 1. Create User
                new_user = User.objects.create_user(
                    username=final_username, 
                    password=password, 
                    email=email_address # Now this variable is defined!
                )
                print(f"STEP 1: User '{final_username}' created (ID: {new_user.id})")

                # 2. Save Customer Model
                customer = form.save(commit=False)
                customer.user = new_user
                customer.save()
                print("STEP 2: Customer Data saved.")

                # 3. Handle Profile
                from .models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=new_user)
                print(f"STEP 3: Profile retrieved. Created new? {created}")
                print(f"   -> Old Role was: '{profile.role}'")

                # 4. FORCE UPDATE ROLE
                profile.role = 'Customer'
                profile.business = customer.business
                profile.save()
                print(f"STEP 4: Profile saved. Role is NOW: '{profile.role}'")

                # 5. Handle Groups (Just in case Admin Panel looks at Groups)
                from django.contrib.auth.models import Group
                group, _ = Group.objects.get_or_create(name='Customer')
                new_user.groups.add(group)
                print(f"STEP 5: Added to Django Group 'Customer'. Total Groups: {new_user.groups.count()}")

                # 6. Verify Database Readback
                check_profile = UserProfile.objects.get(user=new_user)
                print(f"STEP 6: Read from DB again. Final Role in DB is: '{check_profile.role}'")
                print("=== DEBUGGING END ===\n")
                
                messages.success(request, f"Account created! Login ID: {final_username}")
                return redirect('login')

            except Exception as e:
                print(f"\n!!! CRASH DETECTED !!! Error: {e}")
                if 'new_user' in locals(): 
                    new_user.delete()
                messages.error(request, f"Error: {e}")
    else:
        form = CustomerRegistrationForm()

    form.fields['business'].widget = forms.Select(attrs={'class': 'form-select'})
    form.fields['business'].queryset = LaundryBusiness.objects.all()

    return render(request, 'orders/register.html', {'form': form})

from django.contrib.auth import update_session_auth_hash # Important for keeping them logged in

@login_required
def change_password(request):
    effective_email = request.user.email or ''
    if not effective_email:
        profile = getattr(request.user, 'userprofile', None)
        if profile and profile.business and profile.business.contact_email:
            effective_email = profile.business.contact_email

    if request.method == 'POST':
        method = request.POST.get('auth_method') # We will send this from HTML ('old_pass' or 'otp')

        # --- 🟢 METHOD 1: OLD PASSWORD ---
        if method == 'old_pass':
            old_pass = request.POST.get('old_password')
            new_pass = request.POST.get('new_password')
            confirm_pass = request.POST.get('confirm_password')

            if not request.user.check_password(old_pass):
                messages.error(request, "❌ The Old Password you entered is incorrect.")
            elif new_pass != confirm_pass:
                messages.error(request, "❌ New passwords do not match.")
            else:
                request.user.set_password(new_pass)
                request.user.save()
                update_session_auth_hash(request, request.user) # Keeps user logged in
                messages.success(request, "✅ Password changed successfully using Old Password!")
                return redirect('customer_dashboard')

        # --- 🔵 METHOD 2: EMAIL OTP ---
        elif method == 'otp':
            otp_input = request.POST.get('otp_code')
            new_pass = request.POST.get('new_password_otp')
            confirm_pass = request.POST.get('confirm_password_otp')
            
            # Verify OTP from Session
            session_otp = request.session.get('generated_otp')
            
            if not session_otp or otp_input != session_otp:
                messages.error(request, "❌ Invalid or Expired OTP. Please try again.")
            elif new_pass != confirm_pass:
                messages.error(request, "❌ New passwords do not match.")
            else:
                request.user.set_password(new_pass)
                request.user.save()
                update_session_auth_hash(request, request.user)
                
                # Cleanup
                if 'generated_otp' in request.session: del request.session['generated_otp']
                
                messages.success(request, "✅ Password reset successfully via Email Verification!")
                return redirect('customer_dashboard')

    return render(request, 'orders/change_password.html', {'effective_email': effective_email})
# In orders/views.py

@login_required
def delete_branch(request, branch_id):
    # Security: Only Super Admin can delete branches
    if not request.user.is_superuser:
        messages.error(request, "You are not authorized to delete branches.")
        return redirect('dashboard_redirect')

    # Find the branch and delete it
    branch = get_object_or_404(LaundryBusiness, id=branch_id)
    branch_name = branch.name
    branch.delete()
    
    messages.success(request, f"Branch '{branch_name}' has been deleted successfully.")
    return redirect('super_admin_dashboard')

from django.contrib.auth.decorators import user_passes_test # <--- Make sure this is imported at top

@login_required
# OLD LINE (Delete this): @permission_required('auth.change_user', raise_exception=True)
# NEW LINE (Use this instead):
@user_passes_test(lambda u: u.groups.filter(name__in=['Laundry Owner', 'Branch Manager']).exists() or u.is_superuser)
def edit_staff(request, user_id):
    # 1. Get the user we want to edit
    staff_member = get_object_or_404(User, id=user_id)
    
    # 2. Security Check: Ensure they belong to YOUR branch
    # (We also allow Owners to edit anyone)
    is_owner = request.user.groups.filter(name='Laundry Owner').exists() or request.user.is_superuser
    
    if not is_owner:
        # If not owner, they MUST be in the same branch
        if not hasattr(staff_member, 'userprofile') or \
           staff_member.userprofile.business != request.user.userprofile.business:
            messages.error(request, "You cannot edit staff from other branches.")
            return redirect('manage_staff')

    # 3. Get their current Group (Role) to pre-fill the form
    current_group = staff_member.groups.first()

    if request.method == 'POST':
        form = StaffEditForm(request.POST, instance=staff_member)
        if form.is_valid():
            # Save username changes
            user = form.save()
            
            # --- ROLE UPDATE LOGIC ---
            new_group = form.cleaned_data['role']
            
            # 1. Update Django Group
            user.groups.clear() # Remove old role
            user.groups.add(new_group) # Add new role
            
            # 2. Update Profile Text
            profile = user.userprofile
            if new_group.name == 'Branch Manager':
                profile.role = 'manager'
            else:
                profile.role = new_group.name.lower() # 'staff'
            profile.save()
            
            messages.success(request, f"Staff member updated successfully!")
            return redirect('manage_staff')
    else:
        # Load the form with existing data
        form = StaffEditForm(instance=staff_member, initial={'role': current_group})

    return render(request, 'orders/edit_staff.html', {
        'form': form, 
        'staff_member': staff_member
    })

# In orders/views.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

@login_required
def collect_payment(request, order_id):
    # 1. Get the order
    order = get_object_or_404(Order, id=order_id)
    
    # 2. Security Check (Optional but good)
    # Ensure only Staff/Manager/Owner can do this (not customers!)
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You are not authorized to collect payments.")
        return redirect('dashboard_redirect')

    # 3. Update the Payment Info
    if order.payment_status != 'Paid':
        order.payment_status = 'Paid'
        order.payment_collected_by = request.user  # <--- THIS SAVES THE STAFF NAME
        order.save()
        messages.success(request, f"Payment collected by {request.user.username} for Order #{order.id}")
    else:
        messages.info(request, "This order is already paid.")

    return redirect('dashboard_redirect')

@login_required
def customer_complaint_list(request):
    # 1. Security Check: Ensure user is a customer
    if not hasattr(request.user, 'customer'):
        return redirect('dashboard_redirect')
    
    # 2. Get their complaints (Newest first)
    my_complaints = Complaint.objects.filter(customer=request.user.customer).order_by('-created_at')

    return render(request, 'orders/customer_complaint_list.html', {'complaints': my_complaints})

import random
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# --- 🔥 NEW HELPER VIEW FOR SENDING OTP 🔥 ---
# This is called by Javascript when the user clicks "Verify Email"
@csrf_exempt # Disabling CSRF for simpler AJAX for now (add back in production)
def send_otp_email(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
             return JsonResponse({'status': 'error', 'message': 'Email is required.'})
             
        # 1. Generate a 6-digit random code
        otp_code = str(random.randint(100000, 999999))
        
        # 2. Store it in the session (Temporary storage)
        # We store the code AND the email it was sent to, to prevent tampering.
        request.session['generated_otp'] = otp_code
        request.session['otp_email'] = email
        request.session.set_expiry(300) # OTP expires in 5 minutes (300 seconds)
        
        # 3. Send the Email
        subject = 'Your Laundry Service Verification Code'
        message = f'Hello! Your verification code is: {otp_code}. It expires in 5 minutes.'
        from_email = settings.EMAIL_HOST_USER
        
        if not from_email:
            import logging
            logging.error('EMAIL_HOST_USER is not configured')
            return JsonResponse({'status': 'error', 'message': 'Email service is not configured. Contact administrator.'})
        
        try:
            send_mail(subject, message, from_email, [email], fail_silently=False)
            return JsonResponse({'status': 'success', 'message': 'OTP sent successfully! Check your inbox.'})
        except Exception as e:
            import logging
            logging.error(f'Email Error: {str(e)}')
            return JsonResponse({'status': 'error', 'message': f'Failed to send email: {str(e)}'})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

@csrf_exempt
def verify_registration_otp(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'valid': False, 'message': 'Invalid request.'}, status=405)

    otp_code = str(request.POST.get('otp_code', '')).strip()
    email = str(request.POST.get('email', '')).strip()

    session_otp = str(request.session.get('generated_otp', '')).strip()
    session_email = str(request.session.get('otp_email', '')).strip()

    if not session_otp or not session_email:
        return JsonResponse({
            'status': 'success',
            'valid': False,
            'message': 'OTP expired. Please click Verify again.'
        })

    if not otp_code.isdigit() or len(otp_code) != 6:
        return JsonResponse({
            'status': 'success',
            'valid': False,
            'message': 'Enter a valid 6-digit OTP.'
        })

    if email and session_email.lower() != email.lower():
        return JsonResponse({
            'status': 'success',
            'valid': False,
            'message': 'Email changed. Please click Verify again.'
        })

    is_valid = otp_code == session_otp
    return JsonResponse({
        'status': 'success',
        'valid': is_valid,
        'message': 'OTP verified successfully.' if is_valid else 'Incorrect OTP. Please check and try again.'
    })
# --- MASTER SETTING FOR OTP TIMER ---
OTP_EXPIRY_SECONDS = 300  # Change this to 300 for 5 minutes, 120 for 2 minutes, etc.

def check_username_availability(request):
    username = (request.GET.get('username') or '').strip()
    if not username:
        return JsonResponse({'status': 'error', 'message': 'Username is required.'}, status=400)

    normalized = re.sub(r'[^\w.@+-]+', '', username) or 'customer'
    normalized = normalized[:120]

    is_taken = User.objects.filter(username__iexact=username).exists() or User.objects.filter(username__iexact=normalized).exists()
    suggestions = []

    if is_taken:
        for i in range(1, 8):
            candidate = f"{normalized}{i}"[:150]
            if not User.objects.filter(username__iexact=candidate).exists():
                suggestions.append(candidate)
            if len(suggestions) >= 3:
                break

    return JsonResponse({
        'status': 'success',
        'available': not is_taken,
        'normalized': normalized,
        'suggestions': suggestions,
    })

@csrf_exempt
def send_reset_otp(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        if not username:
            return JsonResponse({'status': 'error', 'message': 'Username is required.'})

        try:
            user = User.objects.get(username=username)
            if not user.email:
                return JsonResponse({'status': 'error', 'message': 'No email linked to this account. Contact admin.'})

            # Check cooldown dynamically
            last_sent = request.session.get('reset_otp_time', 0)
            current_time = time.time()
            if current_time - last_sent < OTP_EXPIRY_SECONDS:
                remaining = int(OTP_EXPIRY_SECONDS - (current_time - last_sent))
                return JsonResponse({'status': 'error', 'message': f'Please wait {remaining} seconds before requesting a new OTP.'})

            # Generate OTP
            otp_code = str(random.randint(100000, 999999))

            # Save to session safely
            request.session['reset_otp'] = otp_code
            request.session['reset_username'] = username
            request.session['reset_otp_time'] = current_time
            request.session.set_expiry(OTP_EXPIRY_SECONDS) # Dynamic expiration

            # Send Email
            minutes = OTP_EXPIRY_SECONDS // 60
            subject = 'Password Reset Verification Code'
            message = f'Hello {user.first_name or username},\n\nYour password reset OTP is: {otp_code}.\nIt expires in {minutes} minute(s).\nIf you did not request this, please ignore this email.'
            from_email = settings.EMAIL_HOST_USER
            
            if not from_email:
                import logging
                logging.error('EMAIL_HOST_USER is not configured')
                return JsonResponse({'status': 'error', 'message': 'Email service is not configured. Contact administrator.'})
            
            try:
                send_mail(subject, message, from_email, [user.email], fail_silently=False)
            except Exception as e:
                import logging
                logging.error(f'Password reset email failed: {str(e)}')
                return JsonResponse({'status': 'error', 'message': f'Failed to send email: {str(e)}'})

            parts = user.email.split('@')
            masked_email = f"{parts[0][0]}***@{parts[1]}"

            # 🔥 THE FIX: Send the expiry time to Javascript!
            return JsonResponse({'status': 'success', 'message': f'OTP sent successfully to {masked_email}', 'expiry_time': OTP_EXPIRY_SECONDS})

        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Username not found.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})


def forgot_password(request):
    context = {'show_step3': False, 'username': '', 'otp_code': ''}

    if request.method == 'POST':
        username = request.POST.get('username', '')
        otp_input = request.POST.get('otp_code', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        context['username'] = username
        context['otp_code'] = otp_input
        context['show_step3'] = True 

        session_otp = request.session.get('reset_otp')
        session_username = request.session.get('reset_username')
        last_sent = request.session.get('reset_otp_time', 0)

        # 1. Final Security Check (Dynamic)
        if time.time() - last_sent > OTP_EXPIRY_SECONDS or otp_input != session_otp or username != session_username:
            messages.error(request, "Security verification failed or OTP expired. Please start over.")
            context['show_step3'] = False
            return render(request, 'orders/forgot_password.html', context)

        # 2. Check Passwords
        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return render(request, 'orders/forgot_password.html', context) 

        # 3. Save New Password
        try:
            user = User.objects.get(username=username)
            user.set_password(new_password)
            user.save()

            if 'reset_otp' in request.session: del request.session['reset_otp']
            if 'reset_username' in request.session: del request.session['reset_username']
            if 'reset_otp_time' in request.session: del request.session['reset_otp_time']

            messages.success(request, "Password reset successfully! You can now log in.")
            return redirect('login')
            
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            context['show_step3'] = False
            return render(request, 'orders/forgot_password.html', context)

    return render(request, 'orders/forgot_password.html', context)


@csrf_exempt
def verify_reset_otp(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        otp_input = str(request.POST.get('otp_code', '')).strip()
        
        session_otp = request.session.get('reset_otp') or request.session.get('generated_otp')
        session_username = request.session.get('reset_username')
        session_email = request.session.get('otp_email')
        last_sent = request.session.get('reset_otp_time', 0)

        # If this is the authenticated password change flow, allow validation by session.
        if session_otp and not username:
            if session_email and request.user.is_authenticated:
                effective_email = request.user.email or ''
                if not effective_email:
                    profile = getattr(request.user, 'userprofile', None)
                    if profile and profile.business and profile.business.contact_email:
                        effective_email = profile.business.contact_email
                if effective_email and effective_email.lower() != session_email.lower():
                    return JsonResponse({'status': 'error', 'message': 'Session email mismatch. Please request a new OTP.'})
            if otp_input != str(session_otp):
                return JsonResponse({'status': 'error', 'message': 'Invalid OTP. Please check your code.'})
            return JsonResponse({'status': 'success', 'message': 'OTP Verified!'})

        # Forgot-password flow requires username + session match.
        if not session_otp or not session_username:
            return JsonResponse({'status': 'error', 'message': 'OTP expired. Please resend.'})
        if time.time() - last_sent > OTP_EXPIRY_SECONDS:
            return JsonResponse({'status': 'error', 'message': 'OTP has expired. Please resend.'})
        if otp_input != str(session_otp) or username != session_username:
            return JsonResponse({'status': 'error', 'message': 'Invalid OTP. Please check your code.'})

        return JsonResponse({'status': 'success', 'message': 'OTP Verified!'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

@login_required
def staff_profile(request):
    if hasattr(request.user, 'customer'):
        return redirect('customer_dashboard')
        
    user_profile = getattr(request.user, 'userprofile', None)
    
    if request.method == 'POST':
        otp_input = request.POST.get('otp_code', '').strip()
        
        session_otp = request.session.get('generated_otp')
        pending_email = request.session.get('pending_new_email') # Grab the email they requested
        
        # 1. Verify OTP exists and matches
        if not session_otp or str(otp_input) != str(session_otp):
            messages.error(request, "Invalid or expired OTP. Email not updated.")
        # 2. Check if session lost the pending email
        elif not pending_email:
            messages.error(request, "Session expired. Please request a new OTP.")
        # 3. Final safety check for duplicates (just in case someone took it in the last 2 minutes)
        elif User.objects.filter(email=pending_email).exclude(id=request.user.id).exists():
            messages.error(request, "This email was just taken by another account.")
        else:
            # Success! Update to the new email
            old_email = request.user.email
            request.user.email = pending_email
            request.user.save()
            messages.success(request, f"Success! Email changed from {old_email} to {pending_email}")
            
            # Cleanup session
            if 'generated_otp' in request.session: del request.session['generated_otp']
            if 'pending_new_email' in request.session: del request.session['pending_new_email']
                
        return redirect('staff_profile')

    return render(request, 'orders/staff_profile.html', {'profile': user_profile})
from django.views.decorators.http import require_POST

@login_required
@require_POST
def send_email_change_otp(request):
    new_email = request.POST.get('new_email', '').strip()
    
    if not new_email:
        return JsonResponse({'status': 'error', 'message': 'New email is required.'})
    if new_email.lower() == request.user.email.lower():
        return JsonResponse({'status': 'error', 'message': 'This is already your current email. Please enter a different one.'})
    # 1. UPFRONT DUPLICATE CHECK
    if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
        return JsonResponse({'status': 'error', 'message': 'This email is already in use by another account.'})

    # 2. CURRENT EMAIL CHECK
    old_email = request.user.email
    if not old_email:
        return JsonResponse({'status': 'error', 'message': 'You do not have a current email to receive the OTP. Ask Admin to update it.'})

    # 3. GENERATE OTP AND SEND TO OLD EMAIL
    otp_code = str(random.randint(100000, 999999))
    
    # Store the OTP and the requested NEW email in the session
    request.session['generated_otp'] = otp_code
    request.session['pending_new_email'] = new_email 
    request.session.set_expiry(OTP_EXPIRY_SECONDS) # Uses your master timer!

    # Send Email
    minutes = OTP_EXPIRY_SECONDS // 60
    subject = 'Security Alert: Email Change Request'
    message = f'Hello {request.user.username},\n\nYou requested to change your account email to: {new_email}.\n\nTo authorize this change, please use this verification code: {otp_code}.\nIt expires in {minutes} minute(s).\n\nIf you did not request this, please change your password immediately.'
    from_email = settings.EMAIL_HOST_USER
    
    # Verify email configuration
    if not from_email:
        import logging
        logging.error('EMAIL_HOST_USER is not configured')
        return JsonResponse({'status': 'error', 'message': 'Email service is not configured on the server. Contact administrator.'})
    
    try:
        send_mail(subject, message, from_email, [old_email], fail_silently=False)
        
        # Mask the old email for the success message
        parts = old_email.split('@')
        masked_old = f"{parts[0][:2]}***@{parts[1]}"
        
        return JsonResponse({'status': 'success', 'message': f'OTP sent securely to your CURRENT email ({masked_old})'})
    except Exception as e:
        import logging
        logging.error(f'Email sending failed: {str(e)}')
        return JsonResponse({'status': 'error', 'message': f'Failed to send email: {str(e)}'})


def public_home(request):
    # 1. Handle Logged-In Users
    if request.user.is_authenticated:
        try:
            role = request.user.userprofile.role
        except:
            role = ''
        if role == 'Customer' or hasattr(request.user, 'customer'):
            return redirect('customer_dashboard')
        else:
            return redirect('order_list')

    # 2. Fetch active branches and calculate service averages per branch
    active_branches = LaundryBusiness.objects.filter(is_active=True).order_by('name')

    branches_data = []

    for branch in active_branches:
        services_query = Service.objects.filter(
            business=branch
        ).values('name', 'unit', 'category').annotate(avg_price=Avg('price')).order_by('avg_price')[:5]

        branch_services = []
        for s in services_query:
            short_unit = str(s['unit']).replace('Per ', '').replace('Piece', 'pc').lower()
            avg_price = s['avg_price'] if s['avg_price'] is not None else 0

            branch_services.append({
                'name': s['name'].title(),
                'category': s['category'],
                'price': int(avg_price),
                'unit': short_unit
            })

        branches_data.append({
            'name': (branch.name or 'Branch').strip().title(),
            'address': (branch.address or 'Address not available').strip(),
            'services': branch_services,
        })

    # Backward-compatible alias used by existing template loops
    cities_data = branches_data
    # ... (Your existing city loop code ends here) ...

# 3. Fetch Top Approved Reviews (Only 4 or 5 stars, text is optional!)
    approved_reviews = Order.objects.filter(
        is_review_approved=True, 
        rating__gte=4,
        customer__isnull=False
    ).order_by('-order_date')[:3]
    
    # Generate the stars for the HTML
    for r in approved_reviews:
        r.filled_stars = range(r.rating)
        r.empty_stars = range(5 - r.rating)

    # 🔥 THE MOST IMPORTANT LINE: Make sure 'approved_reviews' is inside these brackets!
    return render(request, 'orders/public_home.html', {
        'branches_data': branches_data,
        'cities_data': cities_data, 
        'approved_reviews': approved_reviews
    })

    # return render(request, 'orders/public_home.html', {'cities_data': cities_data})

@login_required
def manage_reviews(request):
    # 1. Super Admins get to see ALL reviews from ALL branches
    if request.user.is_superuser or getattr(request.user.userprofile, 'role', '') == 'super_admin':
        reviews = Order.objects.filter(
            rating__isnull=False
        ).order_by('is_review_approved', '-order_date')
        
    # 2. Owners and Branch Managers only see reviews for their assigned branch
    elif hasattr(request.user, 'userprofile') and request.user.userprofile.business and request.user.userprofile.role in ['owner', 'branch_manager']:
        reviews = Order.objects.filter(
            business=request.user.userprofile.business, 
            rating__isnull=False
        ).order_by('is_review_approved', '-order_date')
        
    # 3. Regular Staff and Customers get blocked
    else:
        messages.error(request, "You do not have permission to manage reviews.")
        return redirect('order_list')
        
    return render(request, 'orders/manage_reviews.html', {'reviews': reviews})


@login_required
def toggle_review_approval(request, order_id):
    # Get the specific order review
    order = get_object_or_404(Order, id=order_id)
    
    # 1. Check if user is a Super Admin
    is_superuser = request.user.is_superuser or getattr(request.user.userprofile, 'role', '') == 'super_admin'
    
    # 2. Check if user is an Owner/Manager for THIS specific branch
    is_authorized_branch_staff = (
        hasattr(request.user, 'userprofile') and 
        request.user.userprofile.business == order.business and 
        request.user.userprofile.role in ['owner', 'branch_manager']
    )
                          
    # 3. Block unauthorized clicks
    if not (is_superuser or is_authorized_branch_staff):
        messages.error(request, "Security Alert: You do not have permission to approve this review.")
        return redirect('manage_reviews')

    # 4. Toggle the approval status safely
    order.is_review_approved = not order.is_review_approved
    order.save()
    
    status = "approved for the public website" if order.is_review_approved else "hidden from the website"
    messages.success(request, f"Review has been {status}.")
    
    return redirect('manage_reviews')
class CustomLoginView(LoginView):
    template_name = 'registration/login.html' # Tell it to use your beautiful template

    def form_valid(self, form):
        # 1. Check if the user clicked the "Remember me" box
        remember_me = self.request.POST.get('remember_me')

        if not remember_me:
            # If NOT checked: Session expires the moment they close their browser window
            self.request.session.set_expiry(0)
        else:
            # If CHECKED: Keep them logged in for 2 weeks (1,209,600 seconds)
            self.request.session.set_expiry(1209600)

        # 2. Continue logging them in normally
        return super().form_valid(form)