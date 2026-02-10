from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate,login
from django.shortcuts import render,redirect
from ..models import Admin
from ..models import User
from django.views.decorators.csrf import csrf_exempt
from ..password_utils import check_password_hash, migrate_password


class Logincontroller:
    def login_view(request):
        request.session.flush()
        return render(request,'login_form.html')
    def login_post(request):
        if request.method != 'POST':
            return HttpResponse('INVALID REQUEST', status=405)

        email = (request.POST.get('email') or '').strip()
        password = (request.POST.get('password') or '').strip()

        admin = Admin.objects.filter(email__iexact=email).first()
        
        # Use backward-compatible password checking
        if not admin:
            messages.warning(request, 'Invalid email or password')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # Check password using backward-compatible function
        if not check_password_hash(admin.password, password):
            messages.warning(request, 'Invalid email or password')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # Migrate plain-text password to bcrypt hash on successful login
        if admin.password and not admin.password.startswith('$2b$') and not admin.password.startswith('$2a$'):
            migrate_password(admin)

        request.session['admin_id'] = admin.id
        request.session['admin_email'] = admin.email
        # messages.success(request, f"Welcome {admin.email}")
        return redirect('/dashboard')

      
# def login_view(request):
#     print('hi')
#     return HttpResponse('hi')
#     return render(request, 'login_form.html')
    def logout(request):
        request.session.flush()
        messages.warning(request,"you have been logged out")
        return redirect('/login/')
    
    def enter(request):
        return redirect('/login/')
