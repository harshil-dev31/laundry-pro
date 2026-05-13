from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from .models import Area, Branch, Service, Order, Customer, LaundryBusiness
from .email_utils import send_customer_credentials_email
from django.contrib import messages
from django.db.models import Count
from collections import OrderedDict
import re


def _infer_area_name_from_address(address):
    if not address:
        return "Other Area"
    chunks = [part.strip() for part in str(address).split(',') if part.strip()]
    if len(chunks) >= 2:
        return chunks[-2][:100]
    return chunks[0][:100] if chunks else "Other Area"


def _resolve_branch_from_token(branch_token):
    """
    Supports:
    - Real Branch id: "12"
    - Fallback Business token: "biz_7"
    Returns a Branch instance or None.
    """
    if not branch_token:
        return None

    if str(branch_token).startswith("biz_"):
        business_id = str(branch_token).split("biz_", 1)[1]
        if not business_id.isdigit():
            return None

        business = LaundryBusiness.objects.filter(id=int(business_id), is_active=True).first()
        if not business:
            return None

        area_name = _infer_area_name_from_address(business.address)
        area_obj, _ = Area.objects.get_or_create(name=area_name)
        branch_obj, _ = Branch.objects.get_or_create(
            business=business,
            name=business.name,
            defaults={
                'area': area_obj,
                'address': business.address or "Address not available",
            },
        )

        if branch_obj.area_id != area_obj.id or (business.address and branch_obj.address != business.address):
            branch_obj.area = area_obj
            if business.address:
                branch_obj.address = business.address
            branch_obj.save(update_fields=['area', 'address'])

        return branch_obj

    if str(branch_token).isdigit():
        return Branch.objects.filter(id=int(branch_token)).first()

    return None

def quick_booking_view(request):
    return render(request, 'orders/quick_booking.html')

def quick_booking_submit(request):
    if request.method != 'POST':
        return redirect('quick_booking')

    branch_token = request.POST.get('branch')
    if not branch_token:
        messages.error(request, 'Please select a branch to continue.')
        return redirect('quick_booking')

    branch = _resolve_branch_from_token(branch_token)
    if not branch:
        messages.error(request, 'Selected branch does not exist.')
        return redirect('quick_booking')

    name = (request.POST.get('name') or '').strip()
    mobile = (request.POST.get('mobile') or '').strip()
    email = (request.POST.get('email') or '').strip()
    address = (request.POST.get('address') or '').strip()
    if not name or not address or not mobile.isdigit() or len(mobile) != 10 or not email or '@' not in email:
        messages.error(request, 'Please enter valid name, email, mobile number, and pickup address.')
        return redirect('quick_booking')

    request.session['quick_booking'] = {
        'area': request.POST.get('area'),
        'branch': branch.id,
        'name': name,
        'mobile': mobile,
        'email': email,
        'address': address,
    }
    request.session.pop('quick_booking_cart', None)
    return redirect('price_chart', branch_id=branch.id)

def get_areas(request):
    # Source 1: real Area table with active branches
    db_areas = list(
        Area.objects.annotate(
            branch_count=Count('branches', distinct=True)
        ).filter(
            branch_count__gt=0,
            branches__business__is_active=True
        ).values('id', 'name').distinct()
    )

    area_map = {}
    for area in db_areas:
        area_map[area['name'].strip().lower()] = {
            'id': area['id'],
            'name': area['name'].strip(),
        }

    # Source 2: infer areas from active business addresses (merge, don't replace)
    for business in LaundryBusiness.objects.filter(is_active=True).only('address'):
        area_name = _infer_area_name_from_address(business.address).strip()
        key = area_name.lower()
        if key not in area_map:
            area_map[key] = {'id': f'fallback_{key}', 'name': area_name}

    return JsonResponse(sorted(area_map.values(), key=lambda x: x['name'].lower()), safe=False)

def get_branches(request):
    area_id = (request.GET.get('area_id') or '').strip()

    if not area_id:
        return JsonResponse([], safe=False)

    if area_id.startswith('fallback_'):
        area_name = area_id.replace('fallback_', '').strip()
        branches = []
        for business in LaundryBusiness.objects.filter(is_active=True).only('id', 'name', 'address'):
            inferred_area = _infer_area_name_from_address(business.address).lower()
            if inferred_area == area_name:
                branches.append({
                    'id': f'biz_{business.id}',
                    'name': business.name,
                })
        return JsonResponse(sorted(branches, key=lambda b: b['name'].lower()), safe=False)

    if area_id.isdigit():
        branches = list(
            Branch.objects.filter(
                area_id=int(area_id),
                business__is_active=True
            ).values('id', 'name').order_by('name')
        )
        # Also include active businesses that match this area's name but are not in Branch table yet
        area_obj = Area.objects.filter(id=int(area_id)).first()
        if area_obj:
            existing_names = {b['name'].strip().lower() for b in branches}
            inferred = []
            for business in LaundryBusiness.objects.filter(is_active=True).only('id', 'name', 'address'):
                inferred_area = _infer_area_name_from_address(business.address).strip().lower()
                if inferred_area == area_obj.name.strip().lower() and business.name.strip().lower() not in existing_names:
                    inferred.append({'id': f'biz_{business.id}', 'name': business.name})
            branches.extend(inferred)
            branches = sorted(branches, key=lambda b: b['name'].lower())
        return JsonResponse(branches, safe=False)

    return JsonResponse([], safe=False)

def price_chart_view(request, branch_id):
    quick_booking_data = request.session.get('quick_booking')
    if not quick_booking_data:
        messages.error(request, 'Start from Quick Booking to continue.')
        return redirect('quick_booking')

    if int(quick_booking_data.get('branch')) != int(branch_id):
        messages.error(request, 'Selected branch does not match booking session. Please try again.')
        return redirect('quick_booking')

    branch = get_object_or_404(Branch, id=branch_id)
    services = Service.objects.filter(business=branch.business).order_by('category', 'name')
    services_by_category = OrderedDict()
    for service in services:
        services_by_category.setdefault(service.category, []).append(service)

    context = {
        'branch': branch,
        'services': services,
        'services_by_category': services_by_category,
    }
    return render(request, 'orders/price_chart.html', context)

def payment_view(request):
    quick_booking_data = request.session.get('quick_booking')
    if not quick_booking_data:
        messages.error(request, 'Quick booking session expired. Please start again.')
        return redirect('quick_booking')

    branch = get_object_or_404(Branch, id=quick_booking_data['branch'])

    if request.method == 'POST' and request.POST.get('confirm_order') == '1':
        cart = request.session.get('quick_booking_cart', {})
        selected_services = cart.get('items', [])
        if not selected_services:
            messages.error(request, 'No services selected. Please add items first.')
            return redirect('price_chart', branch_id=branch.id)

        selected_payment = request.POST.get('payment_method', cart.get('payment_method', 'Cash'))
        payment_method = selected_payment if selected_payment in {'Cash', 'UPI', 'Card'} else 'Cash'

        customer = Customer.objects.create(
            name=quick_booking_data['name'],
            email=quick_booking_data['email'],
            phone=quick_booking_data['mobile'],
            address=quick_booking_data['address'],
            business=branch.business,
        )

        customer_user = None
        raw_password = None
        quick_email = quick_booking_data.get('email')
        if quick_email:
            clean_name = re.sub(r'[^a-z0-9]', '', quick_booking_data['name'].lower()) or 'user'
            base_username = f"{clean_name}{quick_booking_data['mobile'][-4:]}"
            username = base_username
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{suffix}"
                suffix += 1

            existing_user = User.objects.filter(email=quick_email).first()
            if existing_user is None:
                raw_password = f"{clean_name}@{quick_booking_data['mobile'][-4:]}"
                customer_user = User.objects.create_user(
                    username=username,
                    email=quick_email,
                    password=raw_password,
                    first_name=quick_booking_data['name']
                )
            elif not hasattr(existing_user, 'customer'):
                customer_user = existing_user
            else:
                raw_password = f"{clean_name}@{quick_booking_data['mobile'][-4:]}"
                customer_user = User.objects.create_user(
                    username=username,
                    email=quick_email,
                    password=raw_password,
                    first_name=quick_booking_data['name']
                )

            if customer_user:
                customer.user = customer_user
                customer.save()

                customer_group, _ = Group.objects.get_or_create(name='Customer')
                customer_user.groups.add(customer_group)

        created_order_ids = []
        last_order = None
        for item in selected_services:
            service = Service.objects.filter(id=item['service_id'], business=branch.business).first()
            if not service:
                continue
            order = Order.objects.create(
                customer=customer,
                business=branch.business,
                service=service,
                quantity=item['quantity'],
                is_quick_booking=True,
                temporary_customer=True,
                status='pending',
                payment_method=payment_method,
            )
            created_order_ids.append(order.id)
            last_order = order

        if not last_order:
            messages.error(request, 'Unable to create order. Please try another branch/service set.')
            return redirect('price_chart', branch_id=branch.id)

        request.session['quick_booking_order_ids'] = created_order_ids

        if quick_email and customer_user:
            username = customer_user.username
            password = raw_password
            success, error = send_customer_credentials_email(
                customer_name=customer.name,
                customer_email=quick_email,
                username=username,
                password=password,
            )
            request.session['quick_booking_email_status'] = {
                'sent': success,
                'username': username,
                'password': password,
                'email': quick_email,
                'error': error,
            }

        request.session.pop('quick_booking', None)
        request.session.pop('quick_booking_cart', None)
        return redirect('order_confirmation', order_id=last_order.id)

    if request.method == 'POST':
        selected_services = []
        total_items = 0
        estimated_total = 0

        for key, value in request.POST.items():
            if not key.startswith('quantity_'):
                continue
            try:
                quantity = int(value)
            except (TypeError, ValueError):
                continue
            if quantity <= 0:
                continue

            service_id = key.split('_')[1]
            if not service_id.isdigit():
                continue
            service = Service.objects.filter(id=int(service_id), business=branch.business).first()
            if not service:
                continue

            line_total = float(service.price) * quantity
            selected_services.append({
                'service_id': service.id,
                'name': service.name,
                'unit': service.unit,
                'price': float(service.price),
                'quantity': quantity,
                'line_total': line_total,
            })
            total_items += quantity
            estimated_total += line_total

        if not selected_services:
            messages.error(request, 'Please select at least one service quantity to continue.')
            return redirect('price_chart', branch_id=branch.id)

        payment_method = request.POST.get('payment_method', 'Cash')
        payment_method = payment_method if payment_method in {'Cash', 'UPI', 'Card'} else 'Cash'
        request.session['quick_booking_cart'] = {
            'items': [{'service_id': s['service_id'], 'quantity': s['quantity']} for s in selected_services],
            'payment_method': payment_method,
        }

        return render(request, 'orders/payment.html', {
            'branch': branch,
            'selected_services': selected_services,
            'total_items': total_items,
            'estimated_total': estimated_total,
            'payment_method': payment_method,
            'quick_customer': quick_booking_data,
        })

    cart = request.session.get('quick_booking_cart', {})
    selected_payment = cart.get('payment_method', 'Cash')
    selected_services = []
    total_items = 0
    estimated_total = 0

    for item in cart.get('items', []):
        service = Service.objects.filter(id=item.get('service_id'), business=branch.business).first()
        quantity = int(item.get('quantity', 0))
        if not service or quantity <= 0:
            continue
        line_total = float(service.price) * quantity
        selected_services.append({
            'service_id': service.id,
            'name': service.name,
            'unit': service.unit,
            'price': float(service.price),
            'quantity': quantity,
            'line_total': line_total,
        })
        total_items += quantity
        estimated_total += line_total

    if not selected_services:
        messages.error(request, 'Please choose services first.')
        return redirect('price_chart', branch_id=branch.id)

    return render(request, 'orders/payment.html', {
        'branch': branch,
        'selected_services': selected_services,
        'total_items': total_items,
        'estimated_total': estimated_total,
        'payment_method': selected_payment,
        'quick_customer': quick_booking_data,
    })

def create_quick_booking_order(request):
    return redirect('quick_booking')

def order_confirmation_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    email_status = request.session.pop('quick_booking_email_status', None)
    order_ids = request.session.pop('quick_booking_order_ids', None)
    if order_ids:
        orders = list(Order.objects.filter(id__in=order_ids).order_by('id'))
    else:
        orders = [order]

    total_amount = sum(o.total_price for o in orders)
    return render(request, 'orders/order_confirmation.html', {
        'order': order,
        'orders': orders,
        'total_amount': total_amount,
        'email_status': email_status,
    })
