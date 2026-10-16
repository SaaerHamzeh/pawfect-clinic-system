from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def is_admin(user):
    """Check if user is authenticated and has Admin role or is superuser."""
    return user.is_authenticated and (user.role == user.Role.ADMIN or user.is_superuser)


def is_vet(user):
    """Check if user is authenticated and has Vet role."""
    return user.is_authenticated and user.role == user.Role.VET


def is_staff_member(user):
    """Check if user is authenticated and has Staff role."""
    return user.is_authenticated and user.role == user.Role.STAFF


# --- PERMISSION CHECKERS ---

def can_view_clinical_records(user):
    """All authenticated users can browse medical records."""
    return user.is_authenticated


def can_edit_clinical_records(user):
    """Creating and editing clinical records requires Vet/Admin or explicit can_edit_clinical permission."""
    if not user.is_authenticated:
        return False
    if is_admin(user) or is_vet(user):
        return True
    return user.has_perm("accounts.can_edit_clinical")


def can_manage_clients(user):
    """Adding or editing clients/patients requires Admin, Staff or explicit can_manage_clients permission."""
    if not user.is_authenticated:
        return False
    if is_admin(user) or is_staff_member(user):
        return True
    return user.has_perm("accounts.can_manage_clients")


def can_manage_appointments(user):
    """Creating or editing appointments and reminders requires Admin, Staff or explicit can_manage_appointments permission."""
    if not user.is_authenticated:
        return False
    if is_admin(user) or is_staff_member(user):
        return True
    return user.has_perm("accounts.can_manage_appointments")


def can_view_reports(user):
    """Viewing and exporting reports requires Admin or explicit can_view_reports permission."""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    return user.has_perm("accounts.can_view_reports")


def can_delete_records(user):
    """Deleting records requires Admin or explicit can_delete permission."""
    if not user.is_authenticated:
        return False
    return is_admin(user) or user.has_perm("accounts.can_delete")


def can_restore_records(user):
    """Restoring soft-deleted records requires Admin or explicit can_restore permission."""
    if not user.is_authenticated:
        return False
    return is_admin(user) or user.has_perm("accounts.can_restore")


def can_backup_restore(user):
    """Backing up or restoring data requires Admin or explicit can_backup_restore permission."""
    if not user.is_authenticated:
        return False
    return is_admin(user) or user.has_perm("accounts.can_backup_restore")


def can_access_settings(user):
    """Settings section is visible only if user has access to at least one settings module."""
    if not user.is_authenticated:
        return False
    return is_admin(user) or user.has_perm("accounts.can_backup_restore")


def can_view_all_patients(user):
    """
    Determines if a user can view all patients across the clinic.
    - Admin / Superuser: Always True.
    - Staff: Always True (handles all patients for reception/booking).
    - Vet: True only if granted the 'accounts.view_all_patients' permission.
    """
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if user.role == user.Role.STAFF:
        return True
    if user.role == user.Role.VET:
        return user.has_perm("accounts.view_all_patients")
    return False


def can_view_other_doctors_records(user):
    """
    Determines if a user can view clinical visits and records of other doctors.
    - Admin / Superuser: Always True.
    - Staff: True (handles reception and patient history).
    - Vet: True only if granted the 'accounts.view_all_patients' permission.
    """
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if user.role == user.Role.STAFF:
        return True
    if user.role == user.Role.VET:
        return user.has_perm("accounts.view_all_patients")
    return False


def get_visible_patients(user, queryset=None):
    """
    Returns the queryset of Animal patients visible to the user:
    - Admin, Staff, and Vets with 'view_all_patients' can see all patients.
    - Vets without 'view_all_patients' can only see patients assigned to them
      via appointments, clinical medical records, or vaccination records.
    """
    from apps.patients.models import Animal
    from django.db.models import Q

    if queryset is None:
        queryset = Animal.objects.filter(is_deleted=False)

    if not user.is_authenticated:
        return queryset.none()

    if can_view_all_patients(user):
        return queryset

    if user.role == user.Role.VET:
        return queryset.filter(
            Q(appointments__doctor=user)
            | Q(medical_records__doctor=user)
            | Q(vaccination_records__doctor=user)
        ).distinct()

    return queryset.none()


def get_visible_clinical_records(user, queryset=None):
    """
    Returns the queryset of MedicalRecord instances visible to the user:
    - Admin, Staff, and Vets with 'view_all_patients' can view all records.
    - Vets without 'view_all_patients' can only view records where they are the assigned doctor.
    """
    from apps.clinical.models import MedicalRecord

    if queryset is None:
        queryset = MedicalRecord.objects.alive()

    if not user.is_authenticated:
        return queryset.none()

    if can_view_other_doctors_records(user):
        return queryset

    if user.role == user.Role.VET:
        return queryset.filter(doctor=user)

    return queryset.none()


def get_visible_appointments(user, queryset=None):
    """
    Returns the queryset of Appointment instances visible to the user:
    - Admin, Staff, and Vets with 'view_all_patients' can view all clinic appointments.
    - Vets without 'view_all_patients' can only view their own appointments.
    """
    from apps.appointments.models import Appointment

    if queryset is None:
        queryset = Appointment.objects.alive()

    if not user.is_authenticated:
        return queryset.none()

    if can_view_all_patients(user):
        return queryset

    if user.role == user.Role.VET:
        return queryset.filter(doctor=user)

    return queryset.none()


def can_edit_specific_clinical_record(user, record):
    """
    Admin can edit any record; Vet can only edit records where they are the assigned doctor.
    """
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_vet(user):
        return record.doctor_id == user.pk
    return user.has_perm("accounts.can_edit_clinical")


# --- DECORATORS ---

def admin_required(view_func):
    """Decorator to enforce Admin-only access."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not is_admin(request.user):
            raise PermissionDenied("عذراً، هذه الصفحة مخصصة لمدير النظام (Admin) فقط.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def role_required(*allowed_roles):
    """Decorator to enforce specific user roles."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if is_admin(request.user) or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("ليس لديك الصلاحية المناسبة للوصول إلى هذه الصفحة.")
        return _wrapped_view
    return decorator


def client_manage_permission_required(view_func):
    """Decorator to enforce client & patient creation and editing permission."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not can_manage_clients(request.user):
            raise PermissionDenied("ليس لديك صلاحية إضافة أو تعديل بيانات المالكين والحيوانات.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def appointment_manage_permission_required(view_func):
    """Decorator to enforce appointment & reminder management permission."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not can_manage_appointments(request.user):
            raise PermissionDenied("ليس لديك صلاحية حجز أو تعديل المواعيد والتذكيرات.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def clinical_edit_permission_required(view_func):
    """Decorator to enforce clinical records create/edit permission."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not can_edit_clinical_records(request.user):
            raise PermissionDenied("ليس لديك صلاحية إنشاء أو تعديل السجلات السريرية والمرفقات.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def reports_permission_required(view_func):
    """Decorator to enforce reports view and export permission."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not can_view_reports(request.user):
            raise PermissionDenied("ليس لديك صلاحية عرض التقارير وتصدير ملفات Excel.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def restore_permission_required(view_func):
    """Decorator to enforce restore permission on soft-deleted items."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not can_restore_records(request.user):
            raise PermissionDenied("ليس لديك صلاحية استعادة السجلات المحذوفة.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def delete_permission_required(view_func):
    """Decorator to enforce delete permission on items."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not can_delete_records(request.user):
            raise PermissionDenied("ليس لديك صلاحية حذف السجلات ونقلها إلى سلة المحذوفات.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
