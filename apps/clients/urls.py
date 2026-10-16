from django.urls import path
from . import views

app_name = "clients"

urlpatterns = [
    path("", views.clients, name="list"),
    path("create/", views.client_create, name="create"),
    path("<int:client_id>/", views.client_detail, name="detail"),
    path("<int:client_id>/update/", views.client_update, name="update"),
    path("<int:client_id>/delete/", views.client_delete, name="delete"),
    path("<int:client_id>/hard-delete/", views.client_hard_delete, name="hard_delete"),
    path("<int:client_id>/restore/", views.client_restore, name="restore"),
    path("api/search/", views.client_quick_search, name="api_search"),
    path("bulk-hard-delete/", views.client_bulk_hard_delete, name="bulk_hard_delete"),
]
