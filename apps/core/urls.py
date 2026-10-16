from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/top-patients/", views.top_patients_partial, name="top_patients_partial"),
]
