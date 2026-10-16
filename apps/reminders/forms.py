import datetime
from django import forms
from django.core.exceptions import ValidationError
from .models import Reminder
from apps.patients.models import Animal
from apps.accounts.models import User
from apps.appointments.models import Appointment


class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = [
            "animal",
            "reminder_type",
            "due_date",
            "status",
            "notes",
        ]
        widgets = {
            "animal": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "reminder_type": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "due_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "required": True,
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "سبب التذكير، تفاصيل الجرعة، أو إرشادات المتابعة...",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["animal"].queryset = Animal.objects.alive().select_related("client").order_by("name")
        self.fields["animal"].empty_label = "-- اختر المريض (الحيوان) --"


class ReminderUpdateForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = [
            "reminder_type",
            "due_date",
            "status",
            "notes",
        ]


class ConvertReminderToAppointmentForm(forms.Form):
    """Form to convert a pending reminder into a confirmed appointment."""

    doctor = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.Role.VET, is_active=True).order_by("first_name", "username"),
        empty_label="-- حدد الطبيب البيطري المعالج --",
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                "required": True,
            }
        ),
        label="الطبيب البيطري المعالج",
    )
    date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                "required": True,
            }
        ),
        label="تاريخ الموعد",
    )
    time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={
                "type": "time",
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                "required": True,
            }
        ),
        label="وقت الموعد",
    )
    duration = forms.ChoiceField(
        choices=Appointment.Duration.choices,
        initial=Appointment.Duration.MIN_30,
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                "required": True,
            }
        ),
        label="مدة الموعد",
    )
    brought_by = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                "placeholder": "اسم المرافق في الزيارة إذا لم يكن المالك",
            }
        ),
        label="الشخص المُحضر للحيوان (اختياري)",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                "placeholder": "ملاحظات إضافية للموعد...",
                "rows": 2,
            }
        ),
        label="ملاحظات الموعد",
    )
