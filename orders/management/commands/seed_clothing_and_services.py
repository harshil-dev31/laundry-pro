from django.core.management.base import BaseCommand
from orders.models import ClothingItem, Service, LaundryBusiness

class Command(BaseCommand):
    help = 'Seed database with clothing items and services'

    def handle(self, *args, **options):
        self.stdout.write("🧺 Seeding Clothing Items...")
        
        clothing_data = [
            {'name': 'Shirt', 'icon': 'fa-shirt'},
            {'name': 'T-Shirt', 'icon': 'fa-shirt'},
            {'name': 'Trousers', 'icon': 'fa-pants'},
            {'name': 'Jeans', 'icon': 'fa-pants'},
            {'name': 'Saree', 'icon': 'fa-person'},
            {'name': 'Kurta', 'icon': 'fa-person'},
            {'name': 'Suit', 'icon': 'fa-vest'},
            {'name': 'Jacket', 'icon': 'fa-vest'},
            {'name': 'Bedsheet', 'icon': 'fa-bed'},
            {'name': 'Towel', 'icon': 'fa-water'},
            {'name': 'Salwar Kameez', 'icon': 'fa-person'},
            {'name': 'Dupatta', 'icon': 'fa-scarf'},
        ]
        
        created_count = 0
        for data in clothing_data:
            obj, created = ClothingItem.objects.get_or_create(
                name=data['name'],
                defaults={'icon': data['icon']}
            )
            if created:
                created_count += 1
                self.stdout.write(f"✓ Created: {data['name']}")
            else:
                self.stdout.write(f"→ Already exists: {data['name']}")
        
        self.stdout.write(self.style.SUCCESS(f"✓ {created_count} clothing items created/updated"))
        
        # Get or create default business for services
        business, _ = LaundryBusiness.objects.get_or_create(
            id=1,
            defaults={
                'name': 'Default Branch',
                'owner_name': 'Owner',
                'contact_email': 'contact@laundrypro.com',
                'contact_phone': '1234567890',
                'address': 'Default Address'
            }
        )
        
        self.stdout.write("\n🧼 Seeding Services...")
        
        service_data = [
            {'name': 'Wash', 'price': 15.00},
            {'name': 'Iron', 'price': 12.00},
            {'name': 'Dry Clean', 'price': 120.00},
            {'name': 'Fold', 'price': 8.00},
            {'name': 'Steam Press', 'price': 20.00},
            {'name': 'Starch', 'price': 10.00},
        ]
        
        created_count = 0
        for data in service_data:
            obj, created = Service.objects.get_or_create(
                name=data['name'],
                business=business,
                defaults={'price': data['price']}
            )
            if created:
                created_count += 1
                self.stdout.write(f"✓ Created: {data['name']} - ₹{data['price']}")
            else:
                self.stdout.write(f"→ Already exists: {data['name']}")
        
        self.stdout.write(self.style.SUCCESS(f"✓ {created_count} services created/updated"))
        self.stdout.write(self.style.SUCCESS("\n✓ Database seeding completed!"))
