from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password-reset/", views.password_reset_view, name="password_reset"),
    path("recovery-code/", views.recovery_code_view, name="recovery_code"),
    path("recovery-code/regenerate/", views.regenerate_recovery_code, name="regenerate_recovery_code"),
]
