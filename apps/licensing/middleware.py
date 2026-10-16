import sys
from django.shortcuts import redirect
from .utils import is_system_licensed


class LicenseMiddleware:
    """
    Hardware Node-Locking Enforcement Middleware:
    Ensures the application only runs on the cryptographically authorized device.
    If unlicensed, redirects all traffic to /licensing/activate/.
    """

    EXEMPT_PREFIXES = (
        "/licensing/",
        "/static/",
        "/media/",
        "/favicon.ico",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow testing environment without friction
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            return self.get_response(request)

        path = request.path_info
        is_exempt = any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)

        if is_exempt:
            return self.get_response(request)

        is_licensed, _, _ = is_system_licensed()
        if not is_licensed:
            return redirect("licensing:activate")

        return self.get_response(request)
