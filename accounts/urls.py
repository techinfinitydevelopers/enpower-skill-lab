from django.urls import path

from . import password_reset, views


urlpatterns = [
    path('login/', views.login_view, name='login'),

    # Forgot password. Open to School Admins, Thinking Coaches and Program
    # Coordinators only -- the role check lives in accounts/password_reset.py.
    path('forgot-password/', password_reset.forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', password_reset.reset_password,
         name='reset_password'),
]
