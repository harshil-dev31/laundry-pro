from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0036_service_applicable_items'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='show_on_public',
            field=models.BooleanField(
                default=True,
                help_text='If enabled, this service is visible on the public home pricing section.'
            ),
        ),
    ]

