from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "مدير النظام (Admin)"
        VET = "VET", "طبيب بيطري (Vet)"
        STAFF = "STAFF", "موظف استقبال (Staff)"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
        verbose_name="الدور الأساسي",
    )

    class Meta:
        verbose_name = "مستخدم"
        verbose_name_plural = "المستخدمون"
        permissions = [
            ("can_view_clinical", "عرض السجلات والزيارات السريرية"),
            ("can_edit_clinical", "إنشاء وتعديل السجلات السريرية والمرفقات"),
            ("can_view_reports", "عرض وتصدير التقارير والإحصائيات"),
            ("can_manage_clients", "إضافة وتعديل بيانات المالكين والحيوانات"),
            ("can_manage_appointments", "حجز وإدارة المواعيد والتذكيرات"),
            ("can_delete", "صلاحية حذف السجلات"),
            ("can_restore", "صلاحية استعادة السجلات المحذوفة"),
            ("view_all_patients", "رؤية كافة المرضى للأطباء"),
            ("can_manage_users", "إدارة المستخدمين والصلاحيات"),
            ("can_backup_restore", "النسخ الاحتياطي واستعادة البيانات"),
        ]

    @property
    def is_admin_user(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_vet_user(self):
        return self.role == self.Role.VET

    @property
    def is_staff_user(self):
        return self.role == self.Role.STAFF

    def save(self, *args, **kwargs):
        if self.is_superuser and self.role != self.Role.ADMIN:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            return f"{full_name} ({self.username})"
        return self.username


class PasswordRecoverySettings(models.Model):
    """
    Clinic-wide offline password recovery configuration (singleton id=1).
    Stores only a hash of the recovery code shown to the admin at setup.
    """

    recovery_code_hash = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name="تجزئة رمز استعادة كلمة المرور",
    )
    failed_attempts = models.PositiveIntegerField(default=0, verbose_name="محاولات الاستعادة الفاشلة")
    locked_until = models.DateTimeField(null=True, blank=True, verbose_name="مقفل حتى")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        verbose_name = "إعدادات استعادة كلمة المرور"
        verbose_name_plural = "إعدادات استعادة كلمة المرور"

    def __str__(self):
        return "Password Recovery Settings"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


ROLE_CORE_PERMISSIONS = {
    User.Role.VET: ["can_edit_clinical"],
    User.Role.STAFF: ["can_manage_clients", "can_manage_appointments"],
    User.Role.ADMIN: [
        "can_view_clinical",
        "can_edit_clinical",
        "can_view_reports",
        "can_manage_clients",
        "can_manage_appointments",
        "can_delete",
        "can_restore",
        "view_all_patients",
        "can_manage_users",
        "can_backup_restore",
    ],
}