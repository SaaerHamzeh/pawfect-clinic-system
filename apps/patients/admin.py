from django.contrib import admin
from .models import Animal


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ["name", "species", "breed", "gender", "weight", "client", "is_deleted", "created_at"]
    search_fields = ["name", "breed", "client__full_name", "client__phone"]
    list_filter = ["species", "gender", "is_deleted", "created_at"]
