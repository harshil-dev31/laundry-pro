import logging
import threading
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

def send_branch_credentials_email(owner_name, owner_email, username, password, branch_name):
    """
    Send branch login credentials to the owner's email.
    
    Args:
        owner_name: Full name of the owner
        owner_email: Email address of the owner
        username: Generated username
        password: Generated password
        branch_name: Name of the branch
    """
    if not owner_email:
        logger.error('Branch email failed: owner_email is empty for branch %s', branch_name)
        return False, 'Owner email is missing.'

    if not getattr(settings, 'EMAIL_HOST_USER', None) or not getattr(settings, 'EMAIL_HOST_PASSWORD', None):
        logger.error('Branch email failed: EMAIL sender configuration is missing or incomplete')
        return False, 'Email sender configuration is missing.'

    try:
        context = {
            'owner_name': owner_name,
            'username': username,
            'password': password,
            'branch_name': branch_name,
            'login_url': settings.LOGIN_URL if hasattr(settings, 'LOGIN_URL') else '/accounts/login/',
        }
        
        # Render HTML email template
        html_message = render_to_string('orders/emails/branch_credentials.html', context)
        plain_message = render_to_string('orders/emails/branch_credentials.txt', context)
        
        # Send email
        send_mail(
            subject=f'Your Laundry Pro Branch Account - {branch_name}',
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[owner_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return True, None
    except Exception as e:
        logger.error('Error sending branch credentials email to %s: %s', owner_email, str(e), exc_info=True)
        return False, str(e)


def send_branch_credentials_email_async(owner_name, owner_email, username, password, branch_name):
    """Send branch credentials email in a background thread."""
    thread = threading.Thread(
        target=send_branch_credentials_email,
        args=(owner_name, owner_email, username, password, branch_name),
        daemon=True
    )
    thread.start()
    return thread


def send_customer_credentials_email(customer_name, customer_email, username, password):
    """Send customer account credentials email after quick booking."""
    if not customer_email:
        logger.error('Customer email failed: customer_email is empty for %s', customer_name)
        return False, 'Customer email is missing.'

    if not getattr(settings, 'EMAIL_HOST_USER', None) or not getattr(settings, 'EMAIL_HOST_PASSWORD', None):
        logger.error('Customer email failed: EMAIL sender configuration is missing or incomplete')
        return False, 'Email sender configuration is missing.'

    try:
        context = {
            'customer_name': customer_name,
            'username': username,
            'password': password,
            'login_url': settings.LOGIN_URL if hasattr(settings, 'LOGIN_URL') else '/accounts/login/',
        }

        html_message = render_to_string('orders/emails/customer_credentials.html', context)
        plain_message = render_to_string('orders/emails/customer_credentials.txt', context)

        send_mail(
            subject='Your Laundry Pro Customer Account',
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[customer_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True, None
    except Exception as e:
        logger.error('Error sending customer credentials email to %s: %s', customer_email, str(e), exc_info=True)
        return False, str(e)


def send_customer_credentials_email_async(customer_name, customer_email, username, password):
    thread = threading.Thread(
        target=send_customer_credentials_email,
        args=(customer_name, customer_email, username, password),
        daemon=True
    )
    thread.start()
    return thread