from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model


class SetupMiddleware:
    """
    Redirects all traffic to the First-Run Setup Wizard (/setup/) if no
    administrator exists in the database.
    Once setup is finished (an active Admin exists), access to /setup/ is locked.
    """

    EXEMPT_PREFIXES = (
        "/setup/",
        "/licensing/",
        "/static/",
        "/media/",
        "/favicon.ico",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Allow exempt static, media, and setup paths
        is_exempt = any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)

        try:
            User = get_user_model()
            has_admin = User.objects.filter(role=User.Role.ADMIN, is_active=True).exists()
        except Exception:
            # During migrations or DB errors, proceed normally
            return self.get_response(request)

        if not has_admin:
            if not is_exempt:
                return redirect("setup:wizard")
        else:
            # Setup already completed: lock down /setup/
            if path.startswith("/setup/"):
                if request.user.is_authenticated:
                    return redirect("core:dashboard")
                return redirect("accounts:login")

        return self.get_response(request)
