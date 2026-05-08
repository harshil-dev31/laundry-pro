from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or update a Django superuser from environment variables or command arguments.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default=None, help='Superuser username')
        parser.add_argument('--email', default=None, help='Superuser email')
        parser.add_argument('--password', default=None, help='Superuser password')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username'] or self._get_env('ADMIN_USERNAME', 'admin')
        email = options['email'] or self._get_env('ADMIN_EMAIL', 'admin@example.com')
        password = options['password'] or self._get_env('ADMIN_PASSWORD', '123')

        if not username or not password:
            raise ValueError('Username and password are required to create the admin user.')

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

        action = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(f"Admin user '{username}' {action}."))

    def _get_env(self, key, default=None):
        return __import__('os').environ.get(key, default)
