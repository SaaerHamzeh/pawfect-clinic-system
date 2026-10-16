from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Audit Log model tracking important actions within the clinic system."""

    class Action(models.TextChoices):
        CREATE = "CREATE", "إنشاء (Create)"
        UPDATE = "UPDATE", "تعديل (Update)"
        DELETE = "DELETE", "حذف (Delete)"
        RESTORE = "RESTORE", "استعادة (Restore)"
        LOGIN = "LOGIN", "تسجيل دخول (Login)"
        LOGOUT = "LOGOUT", "تسجيل خروج (Logout)"
        BACKUP = "BACKUP", "نسخ احتياطي (Backup)"
        PERMISSION_CHANGE = "PERMISSION_CHANGE", "تغيير صلاحيات (Permission Change)"
        EXPORT = "EXPORT", "تصدير بيانات (Export)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="المستخدم المنفذ",
    )
    action = models.CharField(
        max_length=50,
        choices=Action.choices,
        db_index=True,
        verbose_name="العملية",
    )
    entity_type = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="نوع الكيان / المورد",
    )
    entity_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="معرف الكيان",
    )
    description = models.TextField(blank=True, verbose_name="تفاصيل العملية")
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="عنوان IP (محلي)",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="تاريخ ووقت العملية",
    )

    class Meta:
        verbose_name = "سجل عملية"
        verbose_name_plural = "سجل العمليات"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        user_name = self.user.username if self.user else "System/Anonymous"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {user_name} -> {self.get_action_display()} ({self.entity_type} #{self.entity_id})"

    @classmethod
    def log(
        cls,
        user,
        action,
        entity=None,
        entity_id=None,
        description="",
        ip_address=None,
        entity_type=None,
    ):
        """Convenience class method to record an audit log entry."""
        if entity and not entity_id and hasattr(entity, "pk"):
            entity_id = str(entity.pk)

        if entity_type is None:
            if entity and isinstance(entity, models.Model):
                entity_type = entity._meta.verbose_name
            else:
                entity_type = str(entity or "Unknown")

        return cls.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ""),
            description=description,
            ip_address=ip_address,
        )
