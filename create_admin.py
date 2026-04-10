import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get('ADMIN_USERNAME', 'admin')
password = os.environ.get('ADMIN_PASSWORD', '123')
email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')

user, created = User.objects.get_or_create(
    username=username,
    defaults={
        'email': email,
        'is_staff': True,
        'is_superuser': True,
    }
)

user.email = email
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()

print(f"Admin user '{username}' {'created' if created else 'updated'}.")
