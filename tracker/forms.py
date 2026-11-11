"""
Authentication, user account, and transaction forms for the tracker application.
"""

from decimal import Decimal
from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import Category, Transaction

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

class TransactionForm(forms.ModelForm):
    """
    Form for logging a new expense transaction adhering to design system tokens.
    """
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        max_value=Decimal('999999.99'),
        widget=forms.NumberInput(attrs={
            'class': 'et-input',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0.01',
            'max': '999999.99',
            'required': True,
        }),
        error_messages={
            'min_value': "Amount must be at least $0.01.",
            'max_value': "Amount cannot exceed $999,999.99.",
        }
    )

    class Meta:
        model = Transaction
        fields = ('category', 'amount', 'tx_date', 'note')
        widgets = {
            'category': forms.Select(attrs={
                'class': 'et-select',
                'required': True,
            }),
            'tx_date': forms.DateInput(
                attrs={
                    'class': 'et-input',
                    'type': 'date',
                    'required': True,
                },
                format='%Y-%m-%d',
            ),
            'note': forms.TextInput(attrs={
                'class': 'et-input',
                'placeholder': 'Optional description (e.g., Grocery run, Coffee)',
                'maxlength': '255',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = "Select a category"
        self.fields['category'].queryset = Category.objects.all().order_by('name')
        if not self.is_bound and 'tx_date' not in self.initial:
            self.initial['tx_date'] = timezone.localdate().isoformat()
        self.fields['note'].required = False

    def clean_note(self):
        """Strip surrounding whitespace and store empty input as None."""
        note = self.cleaned_data.get('note')
        if note:
            note = note.strip()
        return note or None

    def _post_clean(self):
        """
        After model validation completes, attach accessible aria attributes
        pointing to the error element using the bound field's id_for_label.
        """
        super()._post_clean()
        for field_name in self.errors:
            if field_name in self.fields:
                error_id = f"{self[field_name].id_for_label}-error"
                existing = self.fields[field_name].widget.attrs.get('aria-describedby', '')
                if existing and error_id not in existing:
                    describedby = f"{existing} {error_id}".strip()
                elif not existing:
                    describedby = error_id
                else:
                    describedby = existing
                self.fields[field_name].widget.attrs['aria-invalid'] = 'true'
                self.fields[field_name].widget.attrs['aria-describedby'] = describedby
