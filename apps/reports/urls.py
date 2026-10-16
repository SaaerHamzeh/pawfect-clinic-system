from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports, name="list"),
    path("dashboard/", views.reports, name="reports"),
    path("api/client-patients/<int:client_id>/", views.api_client_patients, name="api_client_patients"),
    path("export/patient/<int:patient_id>/", views.export_patient_report, name="export_patient"),
    path("export/client/<int:client_id>/", views.export_client_report, name="export_client"),
    path("export/vaccinations/", views.export_due_vaccinations, name="export_vaccinations"),
    path("export/appointments/", views.export_appointments, name="export_appointments"),
    path("export/directory/", views.export_directory, name="export_directory"),
    path("export/custom/", views.export_custom_unified_report, name="export_custom"),
]
