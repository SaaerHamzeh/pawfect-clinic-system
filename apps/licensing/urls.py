from django.urls import path
from . import views

app_name = "licensing"

urlpatterns = [
    path("activate/", views.activate_view, name="activate"),
]
