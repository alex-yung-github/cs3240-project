from django import forms
from .models import Comment
from .models import Item, Collection, User
from django_select2.forms import Select2MultipleWidget 
from django.core.validators import MaxLengthValidator

class ItemForm(forms.ModelForm):
    description = forms.CharField(
        widget=forms.Textarea,
        max_length=3000,  # approx 500 words (average 6 chars per word)
        help_text="Maximum 500 words (3000 characters)"
    )
    
    class Meta:
        model = Item
        fields = ['title', 'identifier', 'status', 'location', 'description', 'image', 'collections']
        widgets = {
            'collections': forms.CheckboxSelectMultiple(),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'description', 'profile_picture']  # Include the fields we want to update


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['title', 'description', 'visibility', 'allowed_users']
        widgets = {
            'allowed_users': Select2MultipleWidget(attrs={
                'data-placeholder': 'Search for users...',
                'data-minimum-input-length': 0,
            }),
        } 
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['allowed_users'].queryset = User.objects.exclude(id=user.id) if user else User.objects.all()
        
        # If user is a patron, restrict to public collections only
        if user and user.role == 'patron':
            self.fields['visibility'].widget = forms.HiddenInput()
            self.fields['visibility'].initial = 'public'
            
            # Remove allowed_users field for patrons since they can only create public collections
            if 'allowed_users' in self.fields:
                del self.fields['allowed_users']
    

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text', 'rating']
