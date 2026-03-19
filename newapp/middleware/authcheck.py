# newapp/middleware/authcheck.py
from django.shortcuts import redirect
from newapp.models import Admin


class AdminAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or "/"

        # Don't block login, logout, static/media, API webhooks, Super Admin routes, T&C, or Guide
        allowlist = (
            "/login", "/logout", "/static/", "/media/",
            '/get_message', '/send_whatsapp_message', '/send_trigger',
            '/appointment_date', '/create-event', '/api/calendly/webhook',
            '/super-admin/', '/favicon.ico', '/book/', '/booking-confirmed/',
            '/terms/', '/guide/',
        )

        # Check if path is protected
        if not path.startswith(allowlist):
            # NEW: Check Django's built-in auth first
            if request.user.is_authenticated:
                # Check if user has accepted T&C (skip for super admins)
                try:
                    from newapp.models import OrganizationUser
                    org_user = OrganizationUser.objects.get(user=request.user)
                    if not org_user.is_super_admin and not org_user.terms_accepted:
                        return redirect('/terms/')
                except OrganizationUser.DoesNotExist:
                    pass

                # User is logged in via Django auth - allow access
                return self.get_response(request)

            # LEGACY: Check session-based admin auth
            admin_id = request.session.get("admin_id")
            if not admin_id or not Admin.objects.filter(id=admin_id).exists():
                return redirect("/login/")

        return self.get_response(request)
