from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0035_clothingitem_remove_order_customer_note_orderitem_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='applicable_items',
            field=models.ManyToManyField(blank=True, help_text='Clothing items this service can be applied to.', related_name='services', to='orders.clothingitem'),
        ),
    ]

