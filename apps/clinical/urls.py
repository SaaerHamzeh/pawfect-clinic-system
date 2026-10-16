from django.urls import path
from . import views

app_name = "clinical"

urlpatterns = [
    path("", views.clinical_records_list, name="list"),
    path("create/", views.clinical_record_create, name="create"),
    path("<int:record_id>/", views.clinical_record_detail, name="detail"),
    path("<int:record_id>/update/", views.clinical_record_update, name="update"),
    path("<int:record_id>/delete/", views.clinical_record_delete, name="delete"),
    path("<int:record_id>/hard-delete/", views.clinical_record_hard_delete, name="hard_delete"),
    path("<int:record_id>/restore/", views.clinical_record_restore, name="restore"),
    path("bulk-hard-delete/", views.clinical_record_bulk_hard_delete, name="bulk_hard_delete"),
    path("attachments/upload/", views.attachment_upload, name="attachment_upload"),
    path("attachments/<int:attachment_id>/delete/", views.attachment_delete, name="attachment_delete"),
    path("vaccinations/create/", views.vaccination_create, name="vaccination_create"),
    path("vaccinations/<int:vaccination_id>/delete/", views.vaccination_delete, name="vaccination_delete"),
    path("api/today-appointments/", views.today_doctor_appointments_api, name="api_today_appointments"),
]
