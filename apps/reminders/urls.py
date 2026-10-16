from django.urls import path
from . import views

app_name = "reminders"

urlpatterns = [
    path("", views.reminders, name="list"),
    path("create/", views.reminder_create, name="create"),
    path("<int:reminder_id>/update/", views.reminder_update, name="update"),
    path("<int:reminder_id>/convert/", views.reminder_convert_to_appointment, name="convert"),
    path("<int:reminder_id>/status/", views.reminder_update_status, name="update_status"),
    path("<int:reminder_id>/delete/", views.reminder_delete, name="delete"),
    path("<int:reminder_id>/hard-delete/", views.reminder_hard_delete, name="hard_delete"),
    path("<int:reminder_id>/restore/", views.reminder_restore, name="restore"),
    path("bulk-hard-delete/", views.reminder_bulk_hard_delete, name="bulk_hard_delete"),
]
