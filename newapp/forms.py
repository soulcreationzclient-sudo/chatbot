# from django import forms
# from .models import User

# class TaggingForm(forms.Form):
#     tag_name = forms.CharField(label='Tag Name', max_length=100)
#     users = forms.ModelMultipleChoiceField(
#         queryset=User.objects.all(),
#         widget=forms.CheckboxSelectMultiple,
#         label='Select Users'
#     )
# from django import forms
# from .models import Tag, User, UserTag

# class TaggingForm(forms.Form):
#     tag_name = forms.CharField(max_length=150, required=True)
#     users = forms.ModelMultipleChoiceField(
#         queryset=User.objects.all(),
#         required=False,
#         widget=forms.SelectMultiple(attrs={'id': 'id_users', 'class': 'form-control'})
#     )
    
#     def save(self):
#         tag_name = self.cleaned_data['tag_name']
#         users = self.cleaned_data['users']
#         tag, created = Tag.objects.get_or_create(name=tag_name)

#         # Update Tag relations
#         UserTag.objects.filter(tag=tag).delete()
#         for user in users:
#             UserTag.objects.create(tag=tag, user=user)
#         return tag
from django import forms
from .models import User

class TaggingForm(forms.Form):
    tag_name = forms.CharField(max_length=150)
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        # widget=forms.SelectMultiple(attrs={'id': 'id_users', 'class': 'form-control'})
        # widget=forms.SelectMultiple(attrs={'id': 'id_users'})
        widget=forms.CheckboxSelectMultiple  # shows all users as checkboxes
    )
class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'phone_no']  # Add any other fields editable

from django import forms
from .models import AIAgentConfig

class AIAgentConfigForm(forms.ModelForm):
    class Meta:
        model = AIAgentConfig
        fields = ['pdf_file', 'instruction']
