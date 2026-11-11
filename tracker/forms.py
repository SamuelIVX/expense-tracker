"""
Authentication and user account forms for the tracker application.
"""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

class LoginForm(AuthenticationForm):
    """
    Styled login form adhering to design system input tokens.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'et-input',
            'placeholder': 'Enter your username',
            'autofocus': True,
            'autocomplete': 'username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'et-input',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        })

class RegisterForm(UserCreationForm):
    """
    Form for registering a new user account with styled inputs,
    case-insensitive username uniqueness, and password validation.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].widget.attrs.update({
                'class': 'et-input',
                'placeholder': 'Choose a username',
                'autocomplete': 'username',
            })
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.update({
                'class': 'et-input',
                'placeholder': 'Create a password',
                'autocomplete': 'new-password',
            })
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({
                'class': 'et-input',
                'placeholder': 'Confirm your password',
                'autocomplete': 'new-password',
            })
