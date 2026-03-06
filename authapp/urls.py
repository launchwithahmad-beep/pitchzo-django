from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path('auth/register/', views.register_view, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/profile/', views.profile_view, name='profile'),
    path('auth/password-reset/request/', views.password_reset_request_view, name='password_reset_request'),
    path('auth/password-reset/verify-otp/', views.password_reset_verify_otp_view, name='password_reset_verify_otp'),
    path('auth/password-reset/confirm/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('workspaces/', views.workspace_list_create, name='workspace_list_create'),
    path('workspaces/<int:workspace_id>/', views.workspace_detail, name='workspace_detail'),
    path('workspaces/<int:workspace_id>/branding/', views.branding_detail, name='branding_detail'),
]
