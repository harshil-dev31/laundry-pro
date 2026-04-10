from django import forms
from django.contrib.auth.models import Group, Permission
from django.utils import timezone
import re
from .models import Order, Customer, LaundryBusiness, Service, Task, User, StockRequest, PlatformSettings, Complaint, Shift

class RoleForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(), # Populated in __init__
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Access Rights"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Shift Manager'}),
        }

    def __init__(self, *args, **kwargs):
        super(RoleForm, self).__init__(*args, **kwargs)
        
        # 1. Define "Human Readable" Labels for the permissions you care about
        # Format: 'system_codename': 'Friendly Label'
        friendly_names = {
            'add_order': 'Can Create New Orders',
            'delete_order': ' Can Delete Orders (Careful!)',
            'add_user': 'Can Hire New Staff',
            'add_customer': 'Can Register Customers',
            'change_business': ' Can Edit Branch Settings',
            'change_order': ' Can Edit/Update Orders',
        }


        qs = Permission.objects.filter(codename__in=friendly_names.keys())
        
        self.fields['permissions'].queryset = qs
        self.fields['permissions'].label_from_instance = lambda obj: friendly_names.get(obj.codename, obj.name)

from django import forms
from .models import Order, Service, Customer
from django.utils import timezone

# 1. TIME SLOTS LIST
TIME_SLOTS = [
    ('', 'Select Time'),
    ('09:00:00', '09:00 AM'),
    ('10:00:00', '10:00 AM'),
    ('11:00:00', '11:00 AM'),
    ('12:00:00', '12:00 PM'),
    ('13:00:00', '01:00 PM'),
    ('14:00:00', '02:00 PM'),
    ('15:00:00', '03:00 PM'),
    ('16:00:00', '04:00 PM'),
    ('17:00:00', '05:00 PM'),
    ('18:00:00', '06:00 PM'),
    ('19:00:00', '07:00 PM'),
]

class OrderForm(forms.ModelForm):
    pickup_time = forms.ChoiceField(
        choices=TIME_SLOTS, 
        required=False, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Order
        fields = ['customer', 'service', 'quantity', 'pickup_date', 'pickup_time', 'payment_status', 'status', 'notes']
        
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '1'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'service': forms.Select(attrs={'class': 'form-select'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional instructions...'}),
            'pickup_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        
        pre_selected_service = None
        if 'initial' in kwargs and 'service' in kwargs['initial']:
            pre_selected_service = kwargs['initial']['service']

        super(OrderForm, self).__init__(*args, **kwargs)

        # Setup Time & Date
        self.fields['pickup_time'].label = "Preferred Time"
        if 'pickup_time' in self.fields:
            self.fields['pickup_time'].required = False
        if 'pickup_date' in self.fields:
            self.fields['pickup_date'].initial = timezone.now().date()

        # 🔥 100% BULLETPROOF IDENTITY CHECK
        user = self.request.user if self.request else None
        is_staff_logic = False
        
        if user and user.is_authenticated:
            if user.is_superuser:
                is_staff_logic = True
            # We check Groups just like views.py does!
            elif user.groups.filter(name__in=['Branch Manager', 'Laundry Owner', 'Staff']).exists():
                is_staff_logic = True

        # --- DEBUG PRINT TO TERMINAL ---
        print(f"🕵️‍♂️ FORM DEBUG: User='{user}', is_staff_logic={is_staff_logic}")

        # --- LOGIC ---

        # 1. IF "ORDER NOW" WAS CLICKED
        if pre_selected_service:
            self.fields['service'].queryset = Service.objects.filter(id=pre_selected_service.id)
            self.fields['service'].initial = pre_selected_service
            self.fields['service'].empty_label = None 
            self.fields['service'].widget.attrs.update({
                'class': 'form-select bg-light text-dark fw-bold',
                'style': 'pointer-events: none; cursor: default;' 
            })

            if 'payment_status' in self.fields: del self.fields['payment_status']
            if 'status' in self.fields: del self.fields['status']
            
            if not is_staff_logic and 'customer' in self.fields: 
                del self.fields['customer']

        # 2. MANUAL DASHBOARD MODE (Managers & Owners)
        elif is_staff_logic:
            if user.is_superuser:
                if 'service' in self.fields: self.fields['service'].queryset = Service.objects.all()
                if 'customer' in self.fields: self.fields['customer'].queryset = Customer.objects.all()
            elif hasattr(user, 'userprofile') and user.userprofile.business:
                my_business = user.userprofile.business
                if 'customer' in self.fields:
                    self.fields['customer'].queryset = Customer.objects.filter(business=my_business)
                if 'service' in self.fields:
                    self.fields['service'].queryset = Service.objects.filter(business=my_business)

        # 3. FALLBACK (Normal Customers)
        else:
            if hasattr(user, 'customer') and user.customer.business:
                if 'service' in self.fields:
                    self.fields['service'].queryset = Service.objects.filter(business=user.customer.business)
            
            # Since they are a customer, we hide these fields
            if 'customer' in self.fields: del self.fields['customer']
            if 'payment_status' in self.fields: del self.fields['payment_status']
            if 'status' in self.fields: del self.fields['status']
class CustomerRegistrationForm(forms.ModelForm):
    business = forms.ModelChoiceField(queryset=LaundryBusiness.objects.all(), required=False)
    username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    class Meta:
        model = Customer
        fields = ['business','name', 'phone', 'address', 'email']
        widgets = {
            'business': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def _username_suggestions(self, username):
        # Keep only safe username characters and provide practical alternatives.
        base = re.sub(r'[^\w.@+-]+', '', (username or '').strip()) or 'customer'
        base = base[:120]

        suggestions = []
        for i in range(1, 8):
            candidate = f"{base}{i}"[:150]
            if not User.objects.filter(username__iexact=candidate).exists():
                suggestions.append(candidate)
            if len(suggestions) >= 3:
                break

        return suggestions

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "This username already exists. Please try a different username."
            )
        return username

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'address', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}), # Add widget
        }
class LaundryBusinessForm(forms.ModelForm):
    class Meta:
        model = LaundryBusiness
        fields = ['name', 'owner_name', 'contact_email', 'contact_phone', 'address']
        widgets = {
            'name' : forms.TextInput(attrs={'class' : 'form-control'}),
            'owner_name' : forms.TextInput(attrs={'class' : 'form-control'}),
            'contact_email' : forms.EmailInput(attrs={'class' : 'form-control'}),
            'contact_phone' : forms.TextInput(attrs={'class' : 'form-control'}),
            'address' : forms.Textarea(attrs={'class' : 'form-control', 'rows': 3}),
        }
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(LaundryBusinessForm, self).__init__(*args, **kwargs)

        # 2. Check if the user is a Regular Owner (Not a Super Admin)
        if self.user and not self.user.is_superuser:
            self.fields['owner_name'].widget = forms.HiddenInput()
            self.fields['owner_name'].required = False
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'price']
        widgets = {
            'name' : forms.TextInput(attrs={'class' : 'form-control' , 'placeholder': 'e.g. Dry Cleaning'}),
            'price' : forms.NumberInput(attrs={'class' : 'form-control' , 'placeholder': 'e.g. 10.00'}),
        }
from django import forms
from django.contrib.auth.models import User, Group

class StaffCreationForm(forms.Form):
    username = forms.CharField(
        max_length=150, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'New username'})
    )
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control bg-light', 'placeholder': 'staff@example.com'}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    
    # We load the roles dynamically, but filtering happens below
    role = forms.ModelChoiceField(
        queryset=Group.objects.none(), # Empty by default
        empty_label="Select Role",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        # 1. Capture the logged-in user
        user = kwargs.pop('user', None)
        super(StaffCreationForm, self).__init__(*args, **kwargs)

        if user:
            # Start with ALL Groups
            qs = Group.objects.all()

            # --- LEVEL 1: GLOBAL EXCLUSIONS (For Everyone) ---
            # No one should be hiring "Super Admin" or "Customer" from this staff panel
            # "Laundry Owner" is also excluded because Owners are created via Business Registration
            excluded_roles = ['Super Admin', 'Laundry Owner', 'Customer', 'Admin']

            # --- LEVEL 2: CHECK IF USER IS OWNER ---
            is_owner = user.groups.filter(name='Laundry Owner').exists() or user.is_superuser

            # --- LEVEL 3: MANAGER RESTRICTIONS ---
            # If the user is NOT an Owner (meaning they are a Branch Manager),
            # they should NOT see high-level roles.
            if not is_owner:
                # Managers cannot create other Managers or Admins
                excluded_roles.extend(['Branch Manager'])

            # Apply the Final Filter
            self.fields['role'].queryset = qs.exclude(name__in=excluded_roles)
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'assigned_to']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Clean Dryer Filter'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        # We need to filter the "Assigned To" list so it ONLY shows staff from THIS shop
        business = kwargs.pop('business', None)
        super(TaskForm, self).__init__(*args, **kwargs)
        
        if business:
            # ✅ NEW LOGIC:
            # 1. Must belong to this Business
            # 2. Must belong to the 'Staff' Group (Excludes Owners and Managers)
            self.fields['assigned_to'].queryset = User.objects.filter(
                userprofile__business=business, 
                groups__name='Staff'
            )
class StockRequestForm(forms.ModelForm):
    class Meta:
        model = StockRequest
        fields = ['item_name', 'quantity']
        widgets = {
            'item_name':forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. Laundry Detergent'}),
            'quantity':forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 5 liters'})
        }
class PlatformSettingsForm(forms.ModelForm):
    class Meta:
        model = PlatformSettings
        fields = ['site_name', 'maintenance_mode', 'global_announcement']
        widgets = {
            'site_name': forms.TextInput(attrs={'class': 'form-control'}),
            'global_announcement': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }



class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ['staff', 'date', 'shift_name', 'start_time', 'end_time']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shift_name': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(ShiftForm, self).__init__(*args, **kwargs)
        
        # Filter: Managers should only assign shifts to THEIR staff
        if user and hasattr(user, 'userprofile') and user.userprofile.business:
            my_business = user.userprofile.business
            # Show staff from my business, but hide the Owner
            self.fields['staff'].queryset = User.objects.filter(
                userprofile__business=my_business).exclude(groups__name__in=['Laundry Owner', 'Branch Manager', 'Customer'])

class CustomerOrderForm(forms.ModelForm):
    # Add a custom Note field for special instructions
    notes = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 2, 
            'placeholder': 'E.g., Starch the shirt, Remove ink stain...'
        })
    )

    class Meta:
        model = Order
        fields = ['service', 'quantity', 'notes']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': 1}),
        }

    def __init__(self, user, *args, **kwargs):
        super(CustomerOrderForm, self).__init__(*args, **kwargs)
        # "CUSTOM" LOGIC: Filter services to only show the ones from THIS customer's shop
        if user and hasattr(user, 'customer'):
            my_business = user.customer.business
            self.fields['service'].queryset = Service.objects.filter(business=my_business)
            
            # Optional: formatting the dropdown label to show price
            self.fields['service'].label_from_instance = lambda obj: f"{obj.name} (₹{obj.price})"

# ... (CustomerForm and OrderForm are above this) ...

# In orders/forms.py

from django import forms
from .models import Complaint, Order, Customer # <--- ENSURE THIS IMPORT EXISTS


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['customer', 'subject', 'description', 'order']
        # We REMOVE 'order' from widgets here to avoid conflicts
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Late Delivery'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe your issue...'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(ComplaintForm, self).__init__(*args, **kwargs)

        def short_order_label(order):
            # Keep native mobile dropdown width compact by using concise option text.
            service_name = getattr(getattr(order, 'service', None), 'name', 'Service')
            return f"#{order.id} - {service_name}"

        # 1. Force-Create the Order Field (Bypasses all Model restrictions)
        # We start with an empty list to avoid errors if no user is found
        self.fields['order'] = forms.ModelChoiceField(
            queryset=Order.objects.none(),
            widget=forms.Select(attrs={'class': 'form-select'}),
            required=False,
            empty_label="Select Related Order"
        )
        self.fields['order'].label_from_instance = short_order_label

        if user:
            # 2. POPULATE IT FOR CUSTOMER
            if hasattr(user, 'customer'):
                self.fields['customer'].widget = forms.HiddenInput()
                self.fields['customer'].initial = user.customer
                
                # Fetch orders directly
                my_orders = Order.objects.filter(customer=user.customer).order_by('-id')
                # FORCE the queryset
                self.fields['order'].queryset = my_orders
                self.fields['order'].label_from_instance = short_order_label

            # 3. POPULATE IT FOR MANAGER
            elif hasattr(user, 'userprofile') and user.userprofile.business:
                my_business = user.userprofile.business
                self.fields['customer'].queryset = Customer.objects.filter(business=my_business)
                self.fields['customer'].widget = forms.Select(attrs={'class': 'form-select'})
                
                # Fetch orders directly
                my_orders = Order.objects.filter(business=my_business).order_by('-id')
                # FORCE the queryset
                self.fields['order'].queryset = my_orders
                self.fields['order'].label_from_instance = short_order_label
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['rating', 'review']
        widgets = {
            # Simple dropdown for stars (1-5)
            'rating': forms.Select(choices=[
                (5, '⭐⭐⭐⭐⭐ - Excellent'),
                (4, '⭐⭐⭐⭐ - Good'),
                (3, '⭐⭐⭐ - Average'),
                (2, '⭐⭐ - Poor'),
                (1, '⭐ - Terrible')
            ], attrs={'class': 'form-select'}),
            'review': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write your feedback here...'}),
        }

class StaffEditForm(forms.ModelForm):
    role = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=['Branch Manager', 'Staff']),
        required=True,
        label="Select Role",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username','email']  # We only allow editing Username and Role
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }