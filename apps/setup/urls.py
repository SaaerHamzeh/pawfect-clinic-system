from django.urls import path
from . import views

app_name = "setup"

urlpatterns = [
    path("", views.wizard, name="wizard"),
    path("complete/", views.complete_setup, name="complete"),
]
