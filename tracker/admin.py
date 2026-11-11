"""
Admin configuration for tracker models.
"""

from django.contrib import admin
from .models import Category, Transaction

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'color')
    search_fields = ('name',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'amount', 'tx_date', 'created_at')
    list_filter = ('category', 'tx_date')
    search_fields = ('user__username', 'note')
    list_select_related = ('user', 'category')
