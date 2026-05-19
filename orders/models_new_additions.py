# New models to add to orders/models.py

class ClothingItem(models.Model):
    """Represents a type of clothing item (e.g., Shirt, Jeans, Saree)"""
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(
        max_length=50, 
        default="fa-shirt",
        help_text="FontAwesome icon class e.g., 'fa-shirt', 'fa-pants'"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class OrderItem(models.Model):
    """Represents a specific clothing item in an order"""
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    clothing_item = models.ForeignKey(
        ClothingItem, 
        on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(default=1)
    services = models.ManyToManyField(
        Service, 
        through='OrderItemService',
        help_text="Services assigned to this clothing item"
    )
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="quantity × sum of service prices"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.clothing_item.name} (x{self.quantity}) - Order #{self.order.id}"
    
    def calculate_subtotal(self):
        """Recalculate subtotal from services"""
        total = 0
        for item_service in self.orderitemservice_set.all():
            total += item_service.price_at_order
        self.subtotal = total * self.quantity
        return self.subtotal
    
    def save(self, *args, **kwargs):
        # Auto-calculate subtotal on save
        self.calculate_subtotal()
        super().save(*args, **kwargs)


class OrderItemService(models.Model):
    """Through table: Links OrderItem to Service with price snapshot"""
    order_item = models.ForeignKey(
        OrderItem, 
        on_delete=models.CASCADE
    )
    service = models.ForeignKey(
        Service, 
        on_delete=models.CASCADE
    )
    price_at_order = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Price snapshot at time of order"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('order_item', 'service')
    
    def __str__(self):
        return f"{self.order_item.clothing_item.name} - {self.service.name} (₹{self.price_at_order})"
