from django.http import HttpResponse
from django.shortcuts import render,redirect
from ..models import User
from ..models import Message
from django.contrib import messages
from newapp.models import Admin
from datetime import datetime
from django.shortcuts import get_object_or_404
from newapp.forms import UserForm
from django.views.decorators.csrf import csrf_exempt
from newapp.models import User, UserTag




class Contactcontroller:

    def dashboard(request):
        # get admin_id from session
        admin_id = request.session.get("admin_id")

        if not admin_id:
            return redirect("/login")   # or return an error if not logged in

        # filter users by admin_id
        users = User.objects.filter(admin_id=admin_id)

        # Add tags list to each user instance
        for user in users:
            user.tags = [ut.tag.name for ut in UserTag.objects.filter(user=user)]

        return render(request, "contact/dashboard.html", {"users": users})
    
    def add_user(request):
        return render(request,'contact/add_user.html')
    
    @csrf_exempt
    def add_admin_user(request):
        # return HttpResponse('hi')
        if(request.method=='POST'):
            name=(request.POST.get('name').strip() or '').strip()
            phone_no=(request.POST.get('phone_no')or '').strip()
            if name=='' or phone_no=='':
                messages.warning(request,'name and phone fields cannot be empty')
            if(not User.objects.filter(phone_no=phone_no)):
                admin_id=Admin.objects.get(id=request.session.get('admin_id'))
                User.objects.create(
                    admin_id=admin_id,
                    name=name,
                    phone_no=phone_no,
                    created_at=datetime.now()
                )
                messages.success(request,'successfully inserted')
                return redirect(request.META.get("HTTP_REFERER", "contact/add"))
            else:
                 messages.warning(request,'already mobile number exists')
                 return redirect(request.META.get("HTTP_REFERER", "contact/add"))
        else:
            return HttpResponse('not correct method')
    
    def edit_user(request, id):
        user = get_object_or_404(User, id=id)
        if request.method == 'POST':
            form = UserForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                return redirect('show_people')  # Adjust to your user list view
        else:
            form = UserForm(instance=user)
        return render(request, 'contact/edit_user.html', {'form': form, 'user': user})

    def delete_user(request, id):
        user = get_object_or_404(User, id=id)

    # Delete related conversations first to avoid foreign key errors
        user.message_set.all().delete()

    # Delete the user
        user.delete()

    # Redirect to user listing page
        return redirect('show_people')  # replace 'show_people' with your actual user listing url name