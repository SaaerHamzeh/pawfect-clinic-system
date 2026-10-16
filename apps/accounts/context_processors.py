from .permissions import (
    is_admin,
    is_vet,
    is_staff_member,
    can_restore_records,
    can_delete_records,
    can_view_clinical_records,
    can_edit_clinical_records,
    can_view_reports,
    can_manage_clients,
    can_manage_appointments,
    can_backup_restore,
    can_access_settings,
)


def permissions_context(request):
    """Makes granular permissions and role checks universally available across all templates."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "can_delete": False,
            "can_restore": False,
            "can_view_clinical": False,
            "can_edit_clinical": False,
            "can_view_reports": False,
            "can_manage_clients": False,
            "can_manage_appointments": False,
            "can_backup_restore": False,
            "can_access_settings": False,
            "is_admin": False,
            "is_vet": False,
            "is_staff": False,
        }

    return {
        "can_delete": can_delete_records(user),
        "can_restore": can_restore_records(user),
        "can_view_clinical": can_view_clinical_records(user),
        "can_edit_clinical": can_edit_clinical_records(user),
        "can_view_reports": can_view_reports(user),
        "can_manage_clients": can_manage_clients(user),
        "can_manage_appointments": can_manage_appointments(user),
        "can_backup_restore": can_backup_restore(user),
        "can_access_settings": can_access_settings(user),
        "is_admin": is_admin(user),
        "is_vet": is_vet(user),
        "is_staff": is_staff_member(user),
    }
