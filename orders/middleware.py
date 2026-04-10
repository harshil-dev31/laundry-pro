from django.shortcuts import redirect
from django.urls import reverse

class BusinessStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated or request.user.is_superuser:
            return self.get_response(request)

        profile = getattr(request.user, 'userprofile', None)
        
        if profile and profile.business and not profile.business.is_active:
            
            # 👇 NEW: Allow access to 'Logout', 'My Branches', and 'Switch Branch'
            allowed_paths = [
                reverse('business_suspended'),
                reverse('logout'),
                reverse('my_branches'),  # Allow them to see the list
                # We need to allow switching, but since switch URLs have IDs (e.g., /switch/5/),
                # we will check if the path STARTS with /orders/switch-branch/
            ]
            
            # Check if current path is allowed OR if it's a switch action
            is_switching = request.path.startswith('/orders/switch-branch/')
            
            if request.path not in allowed_paths and not is_switching:
                return redirect('business_suspended')

        return self.get_response(request)