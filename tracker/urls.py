"""
URL configuration for the tracker application.
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import LoginForm

# Application endpoint routing.
# Initial endpoint stubs provide URL reverse resolution for templates/base.html
# and are replaced with full views in specs 04 (auth), 05 (add), 06 (dashboard), and 07 (history).
urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('add/', views.add_transaction_view, name='add_transaction'),
    path('history/', views.transaction_history_view, name='transaction_history'),
    path('delete/<int:pk>/', views.delete_transaction_view, name='delete_transaction'),
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        form_class=LoginForm,
        redirect_authenticated_user=True,
    ), name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
