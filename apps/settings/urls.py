from django.urls import path
from . import views
from apps.accounts import views as account_views
from apps.backups import views as backup_views

app_name = "settings"

urlpatterns = [
    path("", views.settings, name="index"),
    path("users/", account_views.user_list, name="users"),
    path("users/create/", account_views.user_create, name="user_create"),
    path("users/<int:user_id>/update/", account_views.user_update, name="user_update"),
    path("users/<int:user_id>/toggle/", account_views.user_toggle_status, name="user_toggle_status"),
    path("users/<int:user_id>/reset-password/", account_views.user_reset_password, name="user_reset_password"),

    # Backup & Disaster Recovery endpoints
    path("backups/", backup_views.backup_list, name="backups"),
    path("backups/create/", backup_views.backup_create, name="backup_create"),
    path("backups/settings/save/", backup_views.backup_settings_save, name="backup_settings_save"),
    path("backups/download/<str:filename>/", backup_views.backup_download, name="backup_download"),
    path("backups/validate/<str:filename>/", backup_views.backup_validate, name="backup_validate"),
    path("backups/restore/<str:filename>/", backup_views.backup_restore, name="backup_restore"),
    path("backups/delete/<str:filename>/", backup_views.backup_delete, name="backup_delete"),

    # Audit Logs
    path("audit-logs/", views.audit_logs, name="audit_logs"),

    # Dynamic Lookups & Custom Categories Management
    path("lookups/", views.lookups_dashboard, name="lookups"),
    path("lookups/species/save/", views.save_species, name="save_species"),
    path("lookups/species/<int:pk>/toggle/", views.toggle_species, name="toggle_species"),
    path("lookups/species/<int:pk>/delete/", views.delete_species, name="delete_species"),

    path("lookups/breeds/save/", views.save_breed, name="save_breed"),
    path("lookups/breeds/<int:pk>/toggle/", views.toggle_breed, name="toggle_breed"),
    path("lookups/breeds/<int:pk>/delete/", views.delete_breed, name="delete_breed"),

    path("lookups/visits/save/", views.save_visit_type, name="save_visit_type"),
    path("lookups/visits/<int:pk>/toggle/", views.toggle_visit_type, name="toggle_visit_type"),
    path("lookups/visits/<int:pk>/delete/", views.delete_visit_type, name="delete_visit_type"),

    path("lookups/appointments/save/", views.save_appointment_type, name="save_appointment_type"),
    path("lookups/appointments/<int:pk>/toggle/", views.toggle_appointment_type, name="toggle_appointment_type"),
    path("lookups/appointments/<int:pk>/delete/", views.delete_appointment_type, name="delete_appointment_type"),

    path("lookups/vaccines/save/", views.save_vaccine, name="save_vaccine"),
    path("lookups/vaccines/<int:pk>/toggle/", views.toggle_vaccine, name="toggle_vaccine"),
    path("lookups/vaccines/<int:pk>/delete/", views.delete_vaccine, name="delete_vaccine"),

    path("lookups/services/save/", views.save_service, name="save_service"),
    path("lookups/services/<int:pk>/toggle/", views.toggle_service, name="toggle_service"),
    path("lookups/services/<int:pk>/delete/", views.delete_service, name="delete_service"),

    # Public/Staff JSON API Endpoints
    path("api/breeds/<str:species_key>/", views.api_species_breeds, name="api_species_breeds"),
    path("api/vaccines/", views.api_vaccines_catalog, name="api_vaccines_catalog"),
]
