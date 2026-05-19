import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from orders.models import Customer, LaundryBusiness

# Get or create a business
business, _ = LaundryBusiness.objects.get_or_create(id=1)

# Create a user
user, created = User.objects.get_or_create(
    username='testcust',
    defaults={
        'email': 'testcust@example.com',
        'first_name': 'Test',
        'last_name': 'Customer',
    }
)

if created:
    user.set_password('testpass123')
    user.save()
    print("✓ User created: testcust")
else:
    print("→ User already exists: testcust")

# Create or update customer profile
customer, created = Customer.objects.get_or_create(
    user=user,
    defaults={
        'name': 'Test Customer',
        'phone': '9999999999',
        'email': 'testcust@example.com',
        'business': business,
        'address': '123 Test Street, Ahmedabad'
    }
)

if created:
    print(f"✓ Customer profile created: {customer.name}")
else:
    print(f"→ Customer profile already exists: {customer.name}")

print("\n=== TEST CREDENTIALS ===")
print("Username: testcust")
print("Password: testpass123")
print("=====================")
