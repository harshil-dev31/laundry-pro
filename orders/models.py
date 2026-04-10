from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class  LaundryBusiness(models.Model):
    name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15)
    address = models.TextField()

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name    


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    
    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE, null=True)
    
    name = models.CharField(max_length=100)
    
    email = models.EmailField(max_length=255, null=True, blank=True)
    
    phone = models.CharField(max_length=15) 
    
    address = models.TextField()

    def __str__(self):
        return self.name
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('owner','Laundry Owner'),
        ('branch_manager','Branch Manager'),
        ('staff','Staff'),
        ('customer', 'Customer')
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')

    def __str__(self):
        return f"{self.user.username} - {self.role}" 

class Service(models.Model):
    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE, null=True)

    CATEGORY_CHOICES = [
        ('Dry Cleaning', 'Dry Cleaning'),
        ('Washing', 'Washing & Laundry'),
        ('Premium', 'Premium / Couture'),
        ('Home', 'Home Care (Curtains/Sofa)'),
        ('Shoes', 'Shoe & Bag Cleaning'),
    ]
    
    UNIT_CHOICES = [
        ('Per Piece', 'Per Piece'),
        ('Per Kg', 'Per Kg'),
        ('Per Pair', 'Per Pair'),
        ('Per Meter', 'Per Meter'),
        ('Per Sq. Ft', 'Per Sq. Ft'),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Washing')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES, default='Per Piece')
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} - ₹{self.price}"

class Order(models.Model):
    is_approved = models.BooleanField(default=False)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    rating = models.IntegerField(null=True, blank=True) # 1 to 5 stars
    review = models.TextField(null=True, blank=True)    # Optional text feedback
    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)
    customer_name_backup = models.CharField(max_length=100, editable=False, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    order_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True, help_text="Special instructions from customer")

    payment_collected_by = models.ForeignKey(
        User,
        related_name='collected_orders', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="The staff member who collected the payment"
    )
    PICKUP_SLOTS = (
        ('Morning', 'Morning (9:00 AM - 12:00 PM)'),
        ('Afternoon', 'Afternoon (12:00 PM - 4:00 PM)'),
        ('Evening', 'Evening (4:00 PM - 8:00 PM)'),
    )

    pickup_date = models.DateField(null=True, blank=True)
    pickup_time = models.TimeField(null=True, blank=True)
    PAYMENT_METHODS = [
        ('Cash', 'Cash'),
        ('UPI', 'UPI'),
        ('Card', 'Card'),
        ('Pending', 'Pending'),
    ]
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='Pending')

    # Your Custom Statuses (KEPT)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('washing', 'Washing'),
        ('ironing', 'Ironing'),
        ('ready', 'Ready For Pickup'),
        ('delivered', 'Delivered')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # --- 2. NEW FIELDS REQUIRED FOR REPORTS (ADDED) ---
    PAYMENT_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Paid', 'Paid'),
    ]
    payment_status = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='Unpaid')

    # CHANGED: 'total_price' is now a Database Column (not just a function)
    # This allows the Report to sum it up instantly.
    # Add this line to track if a review is allowed on the public site
    is_review_approved = models.BooleanField(default=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rating = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
        
    )
    # --- 3. NEW LOGIC (To Calculate Price Automatically) ---
    def save(self, *args, **kwargs):
        # This replaces your old 'def total_price(self)' function.
        # It calculates the price NOW and saves it to the database column.
        if not self.id and self.customer:
            self.customer_name_backup = self.customer.name
        
        if self.service:
            self.total_price = self.service.price * self.quantity
        super(Order, self).save(*args, **kwargs)

    def __str__(self):
        # Check if the customer exists before trying to read their name
        if self.customer:
            return f"Order #{self.id} - {self.customer.name}"
        
        # Fallback if the customer was deleted
        return f"Order #{self.id} - Deleted/Unknown Customer"

class Task(models.Model):
    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE)
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({'Done' if self.is_completed else 'Pending'})"

class StockRequest(models.Model):
    STATUS_CHOICES =[
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected')
    ]
    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)

    item_name = models.CharField(max_length=100)
    quantity = models.CharField(max_length=50)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_name} - {self.status}"
    
class PlatformSettings(models.Model):
    # We usually only have ONE row in this table
    site_name = models.CharField(max_length=100, default="LaundryPro")
    maintenance_mode = models.BooleanField(default=False, help_text="Lock the site for non-admins")
    global_announcement = models.TextField(blank=True, help_text="Message shown on top of every page")

    def __str__(self):
        return "Global Settings"

class Complaint(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    ]

    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True) 
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolution_note = models.TextField(blank=True, null=True, help_text="Manager's reply to the customer")
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.subject} - {self.customer.name}"

class Shift(models.Model):
    business = models.ForeignKey(LaundryBusiness, on_delete=models.CASCADE)
    staff = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    SHIFT_TYPES = [
        ('Morning', 'Morning'),
        ('Afternoon', 'Afternoon'),
        ('Night', 'Night'),
    ]
    
    shift_name = models.CharField(max_length=20, choices=SHIFT_TYPES, default='Morning')  

    def __str__(self):
        return f"{self.staff.username} - {self.date} ({self.shift_name})"