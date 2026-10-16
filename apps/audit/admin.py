from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "entity_type", "entity_id", "ip_address"]
    search_fields = ["user__username", "entity_type", "entity_id", "description"]
    list_filter = ["action", "entity_type", "timestamp"]
    readonly_fields = ["timestamp", "user", "action", "entity_type", "entity_id", "description", "ip_address"]
