from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "address", "is_deleted", "created_at"]
    search_fields = ["full_name", "phone", "address"]
    list_filter = ["is_deleted", "created_at"]
