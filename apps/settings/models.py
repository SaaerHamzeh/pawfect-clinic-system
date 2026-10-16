from django.db import models
from apps.core.models import TimeStampedModel, SoftDeleteModel


class AnimalSpecies(TimeStampedModel, SoftDeleteModel):
    """Species taxonomy (e.g. Cat, Dog, Bird, Rabbit, etc.)"""

    name = models.CharField(max_length=100, unique=True, verbose_name="اسم الفصيل")
    code = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="رمز النظام المرجعي")
    icon = models.CharField(max_length=20, default="🐾", verbose_name="أيقونة / رمز تعبيري")
    is_system = models.BooleanField(default=False, verbose_name="نوع نظام أساسي محمي")
    is_active = models.BooleanField(default=True, verbose_name="مفعل للاختيار")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name = "فصيل حيوان"
        verbose_name_plural = "فصائل الحيوانات"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class AnimalBreed(TimeStampedModel, SoftDeleteModel):
    """Breed taxonomy associated with a specific species."""

    species = models.ForeignKey(
        AnimalSpecies,
        on_delete=models.CASCADE,
        related_name="breeds",
        verbose_name="الفصيل المرتبط",
    )
    name = models.CharField(max_length=100, verbose_name="اسم السلالة")
    is_active = models.BooleanField(default=True, verbose_name="مفعل للاختيار")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name = "سلالة حيوان"
        verbose_name_plural = "سلالات الحيوانات"
        ordering = ["species", "order", "name"]
        unique_together = [["species", "name"]]

    def __str__(self):
        return f"{self.name} ({self.species.name})"

    @classmethod
    def get_species_breeds_map(cls):
        """Returns a dict mapping species code and name to active breed names."""
        mapping = {}
        try:
            from apps.settings.models import AnimalSpecies
            species_qs = AnimalSpecies.objects.filter(is_active=True).prefetch_related("breeds")
            for sp in species_qs:
                breeds = list(
                    sp.breeds.filter(is_active=True).order_by("order", "name").values_list("name", flat=True)
                )
                if sp.code:
                    mapping[sp.code] = breeds
                mapping[sp.name] = breeds
        except Exception:
            pass
        return mapping


class ClinicalVisitType(TimeStampedModel, SoftDeleteModel):
    """Clinical visit / examination category (e.g. General Visit, Checkup, Vaccination, Surgery, etc.)"""

    name = models.CharField(max_length=100, unique=True, verbose_name="اسم نوع الزيارة")
    code = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="رمز النظام المرجعي")
    icon = models.CharField(max_length=20, default="🩺", verbose_name="أيقونة / رمز")
    color = models.CharField(max_length=30, default="#1099a7", verbose_name="لون التمييز")
    requires_vaccine_logic = models.BooleanField(
        default=False,
        verbose_name="تطبيق شروط التطعيم والتذكير الآلي للجرعة القادمة",
    )
    is_system = models.BooleanField(default=False, verbose_name="نوع نظام أساسي محمي")
    is_active = models.BooleanField(default=True, verbose_name="مفعل للاختيار")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name = "نوع زيارة سريرية"
        verbose_name_plural = "أنواع الزيارات السريرية"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class AppointmentTypeConfig(TimeStampedModel, SoftDeleteModel):
    """Appointment category configuration for scheduling & calendar."""

    name = models.CharField(max_length=100, unique=True, verbose_name="اسم نوع الموعد")
    code = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="رمز النظام المرجعي")
    default_duration = models.PositiveIntegerField(default=30, verbose_name="المدة التقديرية بالدقائق")
    color = models.CharField(max_length=30, default="#8b5cf6", verbose_name="لون التقويم")
    is_system = models.BooleanField(default=False, verbose_name="نوع نظام أساسي محمي")
    is_active = models.BooleanField(default=True, verbose_name="مفعل للاختيار")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name = "نوع موعد"
        verbose_name_plural = "أنواع المواعيد"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.default_duration} دقيقة)"


class VaccineCatalogItem(TimeStampedModel, SoftDeleteModel):
    """Standard vaccine catalog with default validity intervals."""

    name = models.CharField(max_length=150, unique=True, verbose_name="اسم اللقاح / التطعيم")
    target_species = models.ForeignKey(
        AnimalSpecies,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccines",
        verbose_name="الفصيل المستهدف (اختياري)",
    )
    default_validity_days = models.PositiveIntegerField(
        default=365,
        verbose_name="المدة الافتراضية للجرعة القادمة (بالأيام)",
        help_text="مثال: 365 يوماً للتطعيمات السنوية، 30 يوماً للجرعات التنشيطية",
    )
    notes = models.TextField(blank=True, verbose_name="إرشادات أو ملاحظات الجرعة")
    is_active = models.BooleanField(default=True, verbose_name="مفعل للاختيار")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name = "لقاح معتمد"
        verbose_name_plural = "دليل اللقاحات المعتمدة"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.default_validity_days} يوم)"


class VisitServiceCatalogItem(TimeStampedModel, SoftDeleteModel):
    """Catalog of clinical services / procedures performable during a visit."""

    name = models.CharField(max_length=150, unique=True, verbose_name="اسم الخدمة / الإجراء")
    default_notes = models.TextField(blank=True, verbose_name="وصف قياسي للخدمة")
    is_active = models.BooleanField(default=True, verbose_name="مفعل للاختيار")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name = "خدمة سريرية معتمدة"
        verbose_name_plural = "دليل الخدمات والإجراءات السريرية"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name
