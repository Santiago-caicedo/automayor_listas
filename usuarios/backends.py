# archivo: usuarios/backends.py

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django_tenants.utils import get_tenant_model

UserModel = get_user_model()
TenantModel = get_tenant_model()

class TenantAuthenticationBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Step 1: Standard username/password authentication
        user = super().authenticate(request, username=username, password=password, **kwargs)

        # If standard auth fails, or no request is provided, stop here
        if user is None or request is None:
            return None

        # Step 2: Tenant Check (Only if standard auth succeeded)
        
        # Get the tenant associated with the domain (e.g., empresa1.localhost -> Empresa object for 'empresa1')
        # We need to handle the case where the tenant might not be found (e.g., accessing the main domain 127.0.0.1)
        # or if it's the public tenant. Superusers should be allowed anywhere.
        
        tenant = getattr(request, 'tenant', None)
        
        # Allow superusers to log in anywhere
        if user.is_superuser:
            return user
            
        # If accessing a tenant domain (not public)
        if tenant and tenant.schema_name != 'public':
            # Check if the authenticated user belongs to this specific tenant
            if user.empresa == tenant:
                return user # User belongs to this tenant, allow login
            else:
                # User is valid, but does NOT belong to this tenant's domain. Reject login.
                return None 
        # If accessing the public schema domain (e.g., 127.0.0.1) and the user is NOT a superuser
        elif tenant and tenant.schema_name == 'public' and not user.is_superuser:
             # Regular users should not log into the public/admin domain, only their tenant domain
             return None
        # Allow login if somehow no tenant was found but standard auth passed (less likely with middleware)
        # Or if it's the public tenant and the user *is* a superuser (already handled above, but safe)
        elif not tenant:
             # This case might indicate a configuration issue, but we rely on standard auth here.
             # Or maybe it's a non-tenant specific page if you add them later.
             # For now, let standard auth decide if no tenant context exists.
             # If you want ONLY tenant logins, you could return None here too.
             return user # Or return None if non-tenant access should be forbidden

        # Default fallback (should ideally not be reached with proper tenant setup)
        return None

    def get_user(self, user_id):
        # Standard method to fetch user by ID
        try:
            return UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None