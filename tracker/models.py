"""
Models for the tracker application.
Defines Category, Transaction, and UserProfile relational entities.
"""

from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class UserProfile(models.Model):
    """
    User settings and profile preferences including customized monthly budget.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    monthly_budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1000.00'),
        validators=[
            MinValueValidator(Decimal('0.01'), message="Budget must be at least $0.01."),
            MaxValueValidator(Decimal('999999.99'), message="Budget cannot exceed $999,999.99."),
        ]
    )

    class Meta:
        verbose_name = 'user profile'
        verbose_name_plural = 'user profiles'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(monthly_budget__gt=0, monthly_budget__lte=Decimal('999999.99')),
                name='chk_profile_budget_pos'
            ),
        ]

    def __str__(self):
        return f"{self.user.username}'s Profile (Budget: ${self.monthly_budget:.2f})"


class Category(models.Model):
    """
    Categorical spending bucket with an associated display color.
    """
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#2D7DD2')

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

class Transaction(models.Model):
    """
    Financial expense entry belonging to a user and category.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01'), message="Amount must be at least $0.01."),
            MaxValueValidator(Decimal('999999.99'), message="Amount cannot exceed $999,999.99."),
        ]
    )
    tx_date = models.DateField()
    note = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-tx_date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'tx_date'], name='idx_tx_user_date'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0, amount__lte=Decimal('999999.99')),
                name='chk_amount_pos'
            ),
        ]

    def __str__(self):
        return f"Transaction #{self.pk or 'new'} - ${self.amount:.2f} ({self.tx_date})"
