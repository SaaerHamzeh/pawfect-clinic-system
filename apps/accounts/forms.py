from django import forms
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import User, ROLE_CORE_PERMISSIONS

PERMISSION_CATEGORIES = [
    {
        "category_name": "إدارة السجلات اليومية والعمليات (إضافة / تعديل)",
        "icon": "📝",
        "description": "صلاحيات إضافة وتحديث البيانات التشغيلية في النظام",
        "permissions": [
            ("can_manage_clients", "إضافة وتعديل بيانات المالكين والحيوانات", "تسمح بإنشاء وتعديل ملفات المربين والحيوانات"),
            ("can_manage_appointments", "حجز وإدارة المواعيد والتذكيرات", "تسمح بحجز المواعيد، تغيير حالتها، وتحويل التذكيرات"),
            ("can_edit_clinical", "إنشاء وتعديل الزيارات السريرية والمرفقات", "تسمح بتوثيق الفحوصات، تسجيل التطعيمات ورفع المرفقات (15MB)"),
        ],
    },
    {
        "category_name": "الحذف والاستعادة (سلة المحذوفات)",
        "icon": "🗑️",
        "description": "صلاحيات الحذف والاسترجاع من سلة المحذوفات",
        "permissions": [
            ("can_delete", "حذف السجلات ونقلها للسلة (Delete)", "تسمح بنقل السجلات إلى سلة المحذوفات"),
            ("can_restore", "استعادة السجلات المحذوفة (Restore)", "صلاحية استرجاع السجلات من سلة المحذوفات"),
        ],
    },
    {
        "category_name": "التقارير والصلاحيات المتقدمة",
        "icon": "📊",
        "description": "صلاحيات رؤية البيانات الشاملة وتصدير التقارير",
        "permissions": [
            ("view_all_patients", "رؤية كافة المرضى وسجلات الأطباء الآخرين (للأطباء البيطريين)", "تتيح للطبيب استعراض كافة حيوانات العيادة وسجلات وزيارات الأطباء الآخرين. في حال عدم تفعيلها، يقتصر وصول الطبيب على مرضاه وسجلاته ومواعيده فقط."),
            ("can_view_reports", "عرض وتصدير التقارير الإحصائية و Excel", "تتيح الدخول لقسم التقارير وتصدير ملفات Excel"),
            ("can_backup_restore", "أخذ واستعادة النسخ الاحتياطية", "تتيح أخذ نسخ احتياطية للبيانات محلياً"),
        ],
    },
]

CUSTOM_PERMISSIONS = [
    ("can_manage_clients", "إضافة وتعديل بيانات المالكين والحيوانات"),
    ("can_manage_appointments", "حجز وإدارة المواعيد والتذكيرات"),
    ("can_edit_clinical", "إنشاء وتعديل الزيارات السريرية والمرفقات"),
    ("can_delete", "حذف السجلات ونقلها للسلة (Delete)"),
    ("can_restore", "استعادة السجلات المحذوفة (Restore)"),
    ("view_all_patients", "رؤية كافة المرضى وسجلات الأطباء الآخرين (للأطباء البيطريين)"),
    ("can_view_reports", "عرض وتصدير التقارير الإحصائية و Excel"),
    ("can_backup_restore", "أخذ واستعادة النسخ الاحتياطية"),
]


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                "placeholder": "••••••••",
                "required": True,
            }
        ),
        label="كلمة المرور",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                "placeholder": "أعد إدخال كلمة المرور للتأكيد...",
                "required": True,
            }
        ),
        label="تأكيد كلمة المرور",
    )
    permissions = forms.MultipleChoiceField(
        choices=CUSTOM_PERMISSIONS,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "rounded text-primary-600 focus:ring-primary-500 border-gray-300 ml-2"}
        ),
        required=False,
        label="الصلاحيات الفردية الممنوحة",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
        ]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "اسم المستخدم (بالأحرف الإنجليزية)",
                    "required": True,
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "الاسم الأول",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "الكنية / اللقب",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "user@pawfectclinic.local",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                    "x-model": "addRole",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "rounded text-primary-600 focus:ring-primary-500 border-gray-300 ml-2"}
            ),
        }

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(f"اسم المستخدم «{username}» مستخدم ومسجل بالفعل في النظام. يرجى اختيار اسم آخر.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("كلمتا المرور غير متطابقتين.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_permissions(user)
        return user

    def save_permissions(self, user):
        selected_perms = self.cleaned_data.get("permissions", [])
        core_perms = ROLE_CORE_PERMISSIONS.get(user.role, [])
        all_perms = set(selected_perms) | set(core_perms)
        content_type = ContentType.objects.get_for_model(User)
        user_perms = Permission.objects.filter(content_type=content_type, codename__in=all_perms)
        user.user_permissions.set(user_perms)


class UserEditForm(forms.ModelForm):
    permissions = forms.MultipleChoiceField(
        choices=CUSTOM_PERMISSIONS,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "rounded text-primary-600 focus:ring-primary-500 border-gray-300 ml-2"}
        ),
        required=False,
        label="الصلاحيات الفردية الممنوحة",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
        ]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "اسم المستخدم (لتسجيل الدخول)",
                    "required": True,
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "rounded text-primary-600 focus:ring-primary-500 border-gray-300 ml-2"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            current_perms = set(self.instance.user_permissions.values_list("codename", flat=True))
            core_perms = set(ROLE_CORE_PERMISSIONS.get(self.instance.role, []))
            self.fields["permissions"].initial = list(current_perms | core_perms)

    def clean_username(self):
        """Allows the admin to rename the login username, keeping it unique (case-insensitive)."""
        username = self.cleaned_data.get("username", "").strip()
        duplicates = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(f"اسم المستخدم «{username}» مستخدم ومسجل بالفعل في النظام. يرجى اختيار اسم آخر.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        if self.instance and self.instance.pk:
            was_active_admin = (self.instance.role == User.Role.ADMIN and self.instance.is_active)
            new_role = cleaned_data.get("role")
            new_is_active = cleaned_data.get("is_active")
            if was_active_admin and (new_role != User.Role.ADMIN or not new_is_active):
                remaining_admins = User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=self.instance.pk).count()
                if remaining_admins == 0:
                    raise forms.ValidationError("لا يمكن تعطيل أو تغيير دور المدير النشط الوحيد في النظام للحفاظ على إمكانية إدارة العيادة.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            selected_perms = self.cleaned_data.get("permissions", [])
            core_perms = ROLE_CORE_PERMISSIONS.get(user.role, [])
            all_perms = set(selected_perms) | set(core_perms)
            content_type = ContentType.objects.get_for_model(User)
            user_perms = Permission.objects.filter(content_type=content_type, codename__in=all_perms)
            user.user_permissions.set(user_perms)
        return user


class AdminPasswordResetForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                "placeholder": "كلمة المرور الجديدة",
                "required": True,
            }
        ),
        label="كلمة المرور الجديدة",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                "placeholder": "تأكيد كلمة المرور",
                "required": True,
            }
        ),
        label="تأكيد كلمة المرور الجديدة",
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("كلمتا المرور غير متطابقتين.")
        return cleaned_data


class OfflineForgotPasswordForm(forms.Form):
    username = forms.CharField(
        label="اسم المستخدم",
        min_length=3,
        widget=forms.TextInput(
            attrs={
                "id": "reset-username",
                "class": "w-full pr-11 pl-4 py-2.5 border border-gray-300 rounded-xl text-sm text-left focus:border-primary-500 focus:ring-2 focus:ring-primary-100 focus:outline-none transition bg-slate-50/50",
                "placeholder": "Username...",
                "dir": "ltr",
                "autocomplete": "username",
            }
        ),
    )
    recovery_code = forms.CharField(
        label="رمز الاستعادة",
        widget=forms.TextInput(
            attrs={
                "id": "reset-recovery-code",
                "class": "w-full pr-11 pl-4 py-2.5 border border-gray-300 rounded-xl text-sm text-left tracking-widest focus:border-primary-500 focus:ring-2 focus:ring-primary-100 focus:outline-none transition bg-slate-50/50",
                "placeholder": "PC-XXXX-XXXX",
                "dir": "ltr",
                "autocomplete": "off",
            }
        ),
    )
    new_password = forms.CharField(
        label="كلمة المرور الجديدة",
        min_length=6,
        widget=forms.PasswordInput(
            attrs={
                "id": "reset-new-password",
                "class": "w-full pr-11 pl-4 py-2.5 border border-gray-300 rounded-xl text-sm text-left focus:border-primary-500 focus:ring-2 focus:ring-primary-100 focus:outline-none transition bg-slate-50/50",
                "placeholder": "••••••••",
                "dir": "ltr",
                "autocomplete": "new-password",
            }
        ),
        error_messages={"min_length": "كلمة المرور يجب أن لا تقل عن 6 خانات."},
    )
    confirm_password = forms.CharField(
        label="تأكيد كلمة المرور",
        widget=forms.PasswordInput(
            attrs={
                "id": "reset-confirm-password",
                "class": "w-full pr-11 pl-4 py-2.5 border border-gray-300 rounded-xl text-sm text-left focus:border-primary-500 focus:ring-2 focus:ring-primary-100 focus:outline-none transition bg-slate-50/50",
                "placeholder": "••••••••",
                "dir": "ltr",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("كلمتا المرور غير متطابقتين.")
        return cleaned_data
