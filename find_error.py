import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from orders.models import Order

print("\n🕵️ STARTING DETECTIVE SCRIPT (V2)...")

# --- 1. FIND ALL STAFF USERS (To help you find the right name) ---
print("Checking available users...")
staff_users = User.objects.filter(groups__name__in=['Staff', 'Branch Manager', 'Laundry Owner'])
for s in staff_users:
    print(f"   Found Staff User: '{s.username}'")

# REPLACE THIS WITH ONE OF THE NAMES PRINTED ABOVE!
target_username = "Harshil"  # <--- I guessed your name from your file path, change if wrong! 

print(f"\nAnalyzing User: {target_username}...")

try:
    user = User.objects.get(username=target_username)
    
    # Check Business Link
    if hasattr(user, 'userprofile') and user.userprofile.business:
        print(f"✅ User '{user.username}' is linked to Shop: '{user.userprofile.business.name}'")
    else:
        print(f"❌ CRITICAL ERROR: '{user.username}' has NO Business assigned!")
        print("   -> Go to Admin > Users > Profile and assign a Business.")

except User.DoesNotExist:
    print(f"❌ Error: Could not find user '{target_username}'. check the list above.")

print("-" * 30)

# --- 2. CHECK THE LAST ORDER (ID #37) ---
# We use .last() to get the most recent one
last_order = Order.objects.last()

if last_order:
    print(f"📦 Last Order Created: ID #{last_order.id}")
    
    # Fix for the previous error: Try .name, then .username, then Unknown
    cust_name = "Unknown"
    if hasattr(last_order.customer, 'name'):
        cust_name = last_order.customer.name
    elif hasattr(last_order.customer, 'username'):
        cust_name = last_order.customer.username
        
    print(f"   - Customer: {cust_name}")
    print(f"   - Status: {last_order.status}")
    
    # THE BIG TEST: IS THE BUSINESS LINKED?
    if last_order.business:
        print(f"✅ Linked to Business: '{last_order.business.name}'")
    else:
        print(f"❌ GHOST ORDER DETECTED! Order #{last_order.id} has NO Business (NULL).")
        print("   -> This is why it is invisible on the dashboard.")
else:
    print("No orders found in database.")

print("🕵️ SCAN COMPLETE.\n")