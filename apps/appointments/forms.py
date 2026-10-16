from django import forms
from django.core.exceptions import ValidationError
from .models import Appointment
from apps.patients.models import Animal
from apps.accounts.models import User
from apps.settings.models import AppointmentTypeConfig


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            "animal",
            "doctor",
            "date",
            "time",
            "duration",
            "appointment_type",
            "vaccine_name",
            "status",
            "brought_by",
            "notes",
        ]
        widgets = {
            "animal": forms.HiddenInput(),
            "doctor": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "required": True,
                }
            ),
            "time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "min": "09:00",
                    "max": "21:45",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "required": True,
                }
            ),
            "duration": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "appointment_type": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "vaccine_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "اسم اللقاح المطلوب (مثال: تطعيم رباعي، سعار...)",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "brought_by": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "اسم المرافق / المُحضر للحيوان إذا لم يكن المالك الدائم",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "سبب الزيارة أو ملاحظات سريرية مبدئية...",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Status defaults to SCHEDULED if not provided
        self.fields["status"].required = False
        self.fields["status"].initial = Appointment.Status.SCHEDULED

        # Limit animals to active/alive records
        self.fields["animal"].queryset = Animal.objects.alive().select_related("client").order_by("name")
        self.fields["animal"].empty_label = "-- اختر المريض (الحيوان) --"

        # Limit doctors to Vet users only
        self.fields["doctor"].queryset = User.objects.filter(
            role=User.Role.VET,
            is_active=True,
        ).order_by("first_name", "username")
        self.fields["doctor"].empty_label = "-- حدد الطبيب البيطري المعالج --"

        # If user is a Vet (and not superuser/admin), pre-set doctor and make field optional in validation
        if user and user.is_authenticated and user.role == User.Role.VET and not user.is_superuser and not getattr(user, "is_admin_user", False):
            self.fields["doctor"].required = False
            self.fields["doctor"].initial = user.pk
            self.initial["doctor"] = user.pk

        # Dynamically load active appointment types
        try:
            active_at = AppointmentTypeConfig.objects.filter(is_active=True).order_by("order", "name")
            if active_at.exists():
                choices = [(at.code or at.name, at.name) for at in active_at]
                self.fields["appointment_type"].choices = choices
        except Exception:
            pass

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        confirm_past = (
            self.data.get("confirm_past_date")
            or self.data.get("confirm_override")
            or self.data.get("override_past_date")
        )

        from django.utils import timezone
        today = timezone.localdate()

        if date and date < today and not confirm_past:
            # Check if new record or date changed to a past date
            if not self.instance.pk or (self.instance.pk and self.instance.date != date):
                self.has_past_date_warning = True
                raise forms.ValidationError({
                    "date": forms.ValidationError(
                        f"تاريخ الموعد ({date}) يقع في الماضي. يرجى تأكيد الحجز إذا كنت تقصد توثيق موعد سابق.",
                        code="past_date",
                    )
                })

        return cleaned_data
