# library/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Book
from .models import ReturnRequest


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "STUDENT"
        if commit: 
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class BookForm(forms.ModelForm):
    
    genres = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter genres as comma-separated or JSON array'}),
        required=False,
        help_text='Example: Fantasy, Adventure, Fiction'
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False
    )
    
    class Meta:
        model = Book
        fields = [
            'title', 'series', 'author', 'rating', 'description', 
            'liked_percent', 'language', 'isbn', 'pages', 'publisher', 
            'publish_date', 'genres', 'quantity', 'cover_img'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Book title'}),
            'series': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Series name (optional)'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Author name'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '5'}),
            'liked_percent': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'language': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., English'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ISBN number'}),
            'pages': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Publisher name'}),
            'publish_date': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'YYYY-MM-DD or Month DD, YYYY'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'cover_img': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }
        help_texts = {
            'isbn': 'Unique International Standard Book Number',
            'cover_img': 'URL to book cover image',
            'liked_percent': 'Percentage of readers who liked this book (0-100)',
        }
        
        

class ReturnRequestForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = []  # Just for creation
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ApproveReturnForm(forms.Form):
    ACTION = [
        ('approve', 'Approve Return'),
        ('reject', 'Reject Return'),
    ]
    action = forms.ChoiceField(choices=ACTION, widget=forms.RadioSelect)
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add notes about book condition or reason for rejection...'}),
        required=False,
        label="Librarian Notes"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        notes = cleaned_data.get('notes')
        
        if action == 'reject' and not notes:
            raise forms.ValidationError("Please provide a reason for rejecting the return request.")
        
        return cleaned_data