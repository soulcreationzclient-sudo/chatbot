"""
Controller for Terms & Conditions and Setup Guide pages.
"""
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.utils import timezone


@csrf_protect
@require_http_methods(["GET", "POST"])
def terms_and_conditions(request):
    """Display Terms & Conditions with checkbox agreement."""
    # If user is logged in and already accepted, redirect to dashboard
    if request.user.is_authenticated:
        try:
            from newapp.models import OrganizationUser
            org_user = OrganizationUser.objects.get(user=request.user)
            if org_user.terms_accepted:
                return redirect('dashboard')
        except Exception:
            pass

    if request.method == 'POST':
        agreed = request.POST.get('agree')
        if agreed:
            # Save acceptance to database if user is logged in
            if request.user.is_authenticated:
                try:
                    from newapp.models import OrganizationUser
                    org_user = OrganizationUser.objects.get(user=request.user)
                    org_user.terms_accepted = True
                    org_user.terms_accepted_at = timezone.now()
                    org_user.save(update_fields=['terms_accepted', 'terms_accepted_at'])
                except Exception:
                    pass
            
            # Also store in session for non-logged-in users viewing standalone
            request.session['terms_accepted'] = True
            
            # Redirect to guide if standalone, dashboard if logged in
            if request.user.is_authenticated:
                return redirect('dashboard')
            return redirect('setup_guide')
        else:
            messages.error(request, 'You must agree to the Terms and Conditions to continue.')
    
    return render(request, 'terms_and_conditions.html')


@require_http_methods(["GET"])
def setup_guide(request):
    """Display the Setup Guide page (requires T&C acceptance)."""
    # Check if terms were accepted (session or database)
    session_accepted = request.session.get('terms_accepted', False)
    db_accepted = False
    
    if request.user.is_authenticated:
        try:
            from newapp.models import OrganizationUser
            org_user = OrganizationUser.objects.get(user=request.user)
            db_accepted = org_user.terms_accepted
        except Exception:
            pass
    
    if not session_accepted and not db_accepted:
        return redirect('terms_and_conditions')
    
    return render(request, 'setup_guide.html')
