# newapp/middleware.py
from django.shortcuts import redirect
from newapp.models import Admin

class AdminAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or "/"

        # Don't block login, logout, or static/media, or API webhooks
        allowlist = ("/login", "/logout", "/static/", "/media/",'/get_message','/send_whatsapp_message','/send_trigger','/appointment_date','/create-event','/api/calendly/webhook')

        # Check if path is protected
        if not path.startswith(allowlist):
            admin_id = request.session.get("admin_id")
            if not admin_id or not Admin.objects.filter(id=admin_id).exists():
                return redirect("/login_view")

        return self.get_response(request)

# newapp/middleware.py
# from django.conf import settings
# from django.shortcuts import redirect
# from newapp.models import Admin

# def _norm(p: str) -> str:
#     """Normalize paths so we don't get bitten by trailing slashes."""
#     if not p:
#         return "/"
#     return p if p == "/" else p.rstrip("/")

# class AdminAuthMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#         # Your original hard-coded allowlist (kept)
#         base_public = {
#             "/login",
#             "/logout",
#             "/static/",
#             "/media/",
#             "/get_message",
#             "/send_whatsapp_message",
#             "/send_trigger",
#             "/favicon.ico",
#             "/robots.txt",
#             "/admin/",
#         }

#         # Login URL itself should never loop
#         login_url = getattr(settings, "LOGIN_URL", "/login_view/")
#         base_public.update({login_url, _norm(login_url)})

#         # Add project-configured public paths from settings.PUBLIC_PATHS
#         cfg_public = set(getattr(settings, "PUBLIC_PATHS", []))

#         # Build a tolerant prefix list (both with & without trailing slash)
#         public = set()
#         for p in base_public.union(cfg_public):
#             public.add(p)
#             public.add(_norm(p))

#         # Store as tuple for fast startswith checks
#         self.public_prefixes = tuple(sorted(public))

#     def __call__(self, request):
#         path = request.path or "/"
#         npath = _norm(path)

#         # Allow any public path (prefix match, tolerant to trailing slash)
#         if any(path.startswith(p) or npath.startswith(_norm(p)) for p in self.public_prefixes):
#             return self.get_response(request)

#         # Session-based admin check (your existing logic)
#         admin_id = request.session.get("admin_id")
#         if admin_id and Admin.objects.filter(id=admin_id).exists():
#             return self.get_response(request)

#         # Otherwise force login
#         return redirect(getattr(settings, "LOGIN_URL", "/login_view/"))
