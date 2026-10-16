from django.urls import path
from . import views

app_name = "appointments"

urlpatterns = [
    path("", views.appointments, name="list"),
    path("api/events/", views.appointments_events_api, name="api_events"),
    path("create/", views.appointment_create, name="create"),
    path("<int:appointment_id>/update/", views.appointment_update, name="update"),
    path("<int:appointment_id>/status/", views.appointment_update_status, name="update_status"),
    path("<int:appointment_id>/delete/", views.appointment_delete, name="delete"),
    path("<int:appointment_id>/hard-delete/", views.appointment_hard_delete, name="hard_delete"),
    path("<int:appointment_id>/restore/", views.appointment_restore, name="restore"),
    path("bulk-hard-delete/", views.appointment_bulk_hard_delete, name="bulk_hard_delete"),
]
