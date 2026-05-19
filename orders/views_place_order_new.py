"""
New views for Place Order functionality
To be appended to orders/views.py
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

@login_required
@require_http_methods(["GET"])
def place_order(request):
    """
    Render the place order form page.
    GET only — displays the interactive order form template
    """
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        messages.error(request, "You must have a customer profile to place orders.")
        return redirect('customer_register')
    
    return render(request, 'orders/place_order.html', {'customer': customer})


@login_required
@require_http_methods(["GET"])
def order_form_data(request):
    """
    API endpoint that returns JSON with clothing items and services.
    Used by the frontend JS to populate the order form.
    """
    # Get all active clothing items
    clothing_items = ClothingItem.objects.filter(is_active=True).values('id', 'name', 'icon')
    
    # Get all active services
    services = Service.objects.filter(is_active=True).values('id', 'name', 'price')
    
    return JsonResponse({
        'success': True,
        'clothing_items': list(clothing_items),
        'services': list(services)
    })


@login_required
@require_http_methods(["POST"])
def submit_order(request):
    """
    Process the submitted order form.
    Expects JSON body with items array and optional special_note.
    """
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Customer profile not found.'
        }, status=400)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body.'
        }, status=400)
    
    # Extract fields
    items = data.get('items', [])
    special_note = data.get('special_note', '').strip()
    
    # Validate: at least 1 item with at least 1 service
    if not items:
        return JsonResponse({
            'success': False,
            'error': 'Please add at least one clothing item to your order.'
        }, status=400)
    
    # Validate each item has at least 1 service
    for item in items:
        service_ids = item.get('service_ids', [])
        if not service_ids:
            return JsonResponse({
                'success': False,
                'error': f'Item {item.get("clothing_item_id")} must have at least one service.'
            }, status=400)
    
    try:
        # Create Order
        order = Order.objects.create(
            customer=customer,
            business=customer.business,
            status='pending',
            payment_status='Unpaid',
            is_approved=False,
            notes=special_note if special_note else None,
            total_price=0  # Will be calculated from items
        )
        
        total_order_price = 0
        
        # Process each item
        for item_data in items:
            clothing_item_id = item_data.get('clothing_item_id')
            quantity = item_data.get('quantity', 1)
            service_ids = item_data.get('service_ids', [])
            
            # Validate clothing item exists
            try:
                clothing_item = ClothingItem.objects.get(id=clothing_item_id, is_active=True)
            except ClothingItem.DoesNotExist:
                order.delete()
                return JsonResponse({
                    'success': False,
                    'error': f'Clothing item {clothing_item_id} not found or inactive.'
                }, status=400)
            
            # Create OrderItem
            order_item = OrderItem.objects.create(
                order=order,
                clothing_item=clothing_item,
                quantity=quantity,
                subtotal=0  # Will be calculated below
            )
            
            item_service_total = 0
            
            # Add services to the order item
            for service_id in service_ids:
                try:
                    service = Service.objects.get(id=service_id, is_active=True)
                except Service.DoesNotExist:
                    order.delete()
                    return JsonResponse({
                        'success': False,
                        'error': f'Service {service_id} not found or inactive.'
                    }, status=400)
                
                # Create OrderItemService with price snapshot
                OrderItemService.objects.create(
                    order_item=order_item,
                    service=service,
                    price_at_order=service.price
                )
                item_service_total += service.price
            
            # Calculate and save subtotal
            order_item.subtotal = item_service_total * quantity
            order_item.save()
            
            total_order_price += order_item.subtotal
        
        # Update order total price
        order.total_price = total_order_price
        order.save()
        
        return JsonResponse({
            'success': True,
            'order_id': order.id
        })
    
    except Exception as e:
        if 'order' in locals() and order.id:
            order.delete()
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def order_detail(request, pk):
    """
    Display detailed view of a specific order with all items and services.
    """
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile required.")
        return redirect('customer_register')
    
    # Get order and ensure customer owns it
    order = get_object_or_404(Order, id=pk, customer=customer)
    
    # Prefetch related items and services for efficiency
    order_items = order.items.prefetch_related(
        'clothing_item',
        'orderitemservice_set__service'
    )
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    
    return render(request, 'orders/order_detail.html', context)
