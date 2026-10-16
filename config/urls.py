from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("clients/", include("apps.clients.urls")),
    path("patients/", include("apps.patients.urls")),
    path("appointments/", include("apps.appointments.urls")),
    path("clinical/", include("apps.clinical.urls")),
    path("reminders/", include("apps.reminders.urls")),
    path("reports/", include("apps.reports.urls")),
    path("settings/", include("apps.settings.urls")),
    path("setup/", include("apps.setup.urls")),
    path("licensing/", include("apps.licensing.urls")),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

handler403 = "apps.core.views.custom_403_view"
handler404 = "apps.core.views.custom_404_view"
handler500 = "apps.core.views.custom_500_view"
