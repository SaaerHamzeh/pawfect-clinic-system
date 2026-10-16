from django.contrib import admin
from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ["animal", "reminder_type", "due_date", "status", "converted_appointment", "is_deleted"]
    search_fields = ["animal__name", "notes"]
    list_filter = ["status", "reminder_type", "due_date", "is_deleted"]
