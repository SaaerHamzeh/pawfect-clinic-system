from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel
from apps.core.validators import validate_phone_number


class Client(TimeStampedModel, SoftDeleteModel):
    """Client / Owner model representing animal owners."""

    full_name = models.CharField(max_length=255, db_index=True, verbose_name="الاسم الكامل")
    phone = models.CharField(
        max_length=30,
        db_index=True,
        validators=[validate_phone_number],
        verbose_name="رقم الهاتف",
    )
    address = models.TextField(blank=True, verbose_name="العنوان")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "عميل"
        verbose_name_plural = "العملاء"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["full_name", "phone"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    @property
    def active_animals_count(self):
        return self.animals.filter(is_deleted=False).count()

    @property
    def secondary_phones(self):
        """Returns non-primary active phone numbers."""
        return self.phone_numbers.filter(is_deleted=False, is_primary=False)

    @property
    def all_phone_numbers(self):
        """Returns all active phone numbers ordered with primary first."""
        return self.phone_numbers.filter(is_deleted=False).order_by("-is_primary", "id")

    def clean(self):
        super().clean()
        if self.phone:
            self.phone = validate_phone_number(self.phone)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def soft_delete(self, timestamp=None):
        now = timestamp or timezone.now()
        super().soft_delete(timestamp=now)
        Animal = self.animals.model
        for animal in Animal.all_objects.filter(client=self, is_deleted=False):
            animal.soft_delete(timestamp=now)
        for phone in self.phone_numbers.filter(is_deleted=False):
            phone.soft_delete(timestamp=now)

    def restore(self):
        client_deleted_at = self.deleted_at
        super().restore()
        if client_deleted_at:
            Animal = self.animals.model
            for animal in Animal.all_objects.filter(
                client=self,
                is_deleted=True,
                deleted_at=client_deleted_at,
            ):
                animal.restore()
            for phone in self.phone_numbers.model.all_objects.filter(
                client=self,
                is_deleted=True,
                deleted_at=client_deleted_at,
            ):
                phone.restore()


class ClientPhone(TimeStampedModel, SoftDeleteModel):
    """Additional phone numbers for a client."""

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="phone_numbers",
        verbose_name="العميل",
    )
    phone = models.CharField(
        max_length=30,
        db_index=True,
        validators=[validate_phone_number],
        verbose_name="رقم الهاتف",
    )
    label = models.CharField(
        max_length=50,
        blank=True,
        default="موبايل",
        verbose_name="تسمية الرقم",
        help_text="مثال: موبايل، واتساب، عمل، هاتف أرضي، هاتف بديل",
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name="رقم أساسي",
    )
    notes = models.CharField(max_length=150, blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "رقم هاتف إضافي"
        verbose_name_plural = "أرقام هواتف العملاء"
        ordering = ["-is_primary", "id"]
        indexes = [
            models.Index(fields=["client", "phone"]),
            models.Index(fields=["phone"]),
        ]

    def __str__(self):
        primary_badge = " [أساسي]" if self.is_primary else ""
        label_badge = f" ({self.label})" if self.label else ""
        return f"{self.phone}{label_badge}{primary_badge}"

    def clean(self):
        super().clean()
        if self.phone:
            self.phone = validate_phone_number(self.phone)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)




