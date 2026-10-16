from django.urls import path
from . import views

app_name = "patients"

urlpatterns = [
    path("", views.patients, name="list"),
    path("api/search/", views.patient_quick_search, name="api_search"),
    path("create/", views.patient_create, name="create"),
    path("<int:patient_id>/", views.patient_detail, name="detail"),
    path("<int:patient_id>/update/", views.patient_update, name="update"),
    path("<int:patient_id>/update-photo/", views.patient_update_photo, name="update_photo"),
    path("<int:patient_id>/delete/", views.patient_delete, name="delete"),
    path("<int:patient_id>/hard-delete/", views.patient_hard_delete, name="hard_delete"),
    path("<int:patient_id>/restore/", views.patient_restore, name="restore"),
    path("bulk-hard-delete/", views.patient_bulk_hard_delete, name="bulk_hard_delete"),
]
