"""
Controller for Terms & Conditions and Setup Guide pages.
"""
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages


@csrf_protect
@require_http_methods(["GET", "POST"])
def terms_and_conditions(request):
    """Display Terms & Conditions with checkbox agreement."""
    if request.method == 'POST':
        agreed = request.POST.get('agree')
        if agreed:
            # Store acceptance in session
            request.session['terms_accepted'] = True
            return redirect('setup_guide')
        else:
            messages.error(request, 'You must agree to the Terms and Conditions to continue.')
    
    return render(request, 'terms_and_conditions.html')


@require_http_methods(["GET"])
def setup_guide(request):
    """Display the Setup Guide page (requires T&C acceptance)."""
    # Check if terms were accepted
    if not request.session.get('terms_accepted', False):
        return redirect('terms_and_conditions')
    
    return render(request, 'setup_guide.html')
