import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from apps.accounts.models import User
from apps.accounts.permissions import (
    is_admin,
    is_vet,
    is_staff_member,
    can_restore_records,
    can_manage_clients,
    can_manage_appointments,
    can_edit_clinical_records,
    get_visible_patients,
    get_visible_clinical_records,
    can_view_all_patients,
    can_view_other_doctors_records,
)
from apps.clients.models import Client as OwnerClient
from apps.patients.models import Animal
from apps.appointments.models import Appointment
from apps.clinical.models import MedicalRecord
from apps.audit.models import AuditLog


class AccountsAuthAndPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_user",
            password="password123",
            role=User.Role.ADMIN,
        )
        self.vet_user = User.objects.create_user(
            username="vet_user",
            password="password123",
            role=User.Role.VET,
        )
        self.staff_user = User.objects.create_user(
            username="staff_user",
            password="password123",
            role=User.Role.STAFF,
        )

    def test_permission_helpers(self):
        self.assertTrue(is_admin(self.admin_user))
        self.assertFalse(is_admin(self.vet_user))
        self.assertTrue(is_vet(self.vet_user))
        self.assertTrue(is_staff_member(self.staff_user))
        self.assertTrue(can_restore_records(self.admin_user))
        self.assertFalse(can_restore_records(self.staff_user))
        # Core role permissions:
        self.assertTrue(can_edit_clinical_records(self.vet_user))
        self.assertTrue(can_manage_clients(self.staff_user))
        self.assertTrue(can_manage_appointments(self.staff_user))
        self.assertFalse(can_edit_clinical_records(self.staff_user))

    def test_login_view_success(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "vet_user",
            "password": "password123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN, user=self.vet_user).exists())

    def test_login_view_invalid_credentials(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "vet_user",
            "password": "wrongpassword",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "غير صحيحة")

    def test_logout_view(self):
        self.client.login(username="vet_user", password="password123")
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGOUT, user=self.vet_user).exists())

    def test_non_admin_cannot_access_user_management(self):
        self.client.login(username="staff_user", password="password123")
        response = self.client.get(reverse("settings:users"))
        self.assertEqual(response.status_code, 403)

    def test_admin_creates_user_with_granular_permissions(self):
        self.client.login(username="admin_user", password="password123")
        post_data = {
            "username": "new_dr_nour",
            "password": "strongpassword123",
            "confirm_password": "strongpassword123",
            "first_name": "نور",
            "last_name": "الهدى",
            "email": "nour@clinic.local",
            "role": User.Role.VET,
            "is_active": "on",
            "permissions": ["can_restore", "view_all_patients"],
        }
        response = self.client.post(reverse("settings:user_create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        new_user = User.objects.filter(username="new_dr_nour").first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.role, User.Role.VET)
        self.assertTrue(new_user.has_perm("accounts.can_restore"))
        self.assertTrue(new_user.has_perm("accounts.view_all_patients"))
        self.assertFalse(new_user.has_perm("accounts.can_backup_restore"))

        # Verify Audit Log
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CREATE, entity_id=str(new_user.pk)).exists())

    def test_add_user_modal_renders_all_create_form_fields(self):
        """Regression: every UserCreateForm field must render inside the add-user modal.

        The template renders the bound form through the context key ``add_form``. When the view
        does not expose that key, Django silently renders empty strings and the modal shows the
        labels with no input boxes at all. Django-rendered widgets are the only elements that
        carry ``id_*`` attributes in this template, which makes them a reliable marker.
        """
        self.client.login(username="admin_user", password="password123")
        response = self.client.get(reverse("settings:users"))
        self.assertEqual(response.status_code, 200)

        self.assertIn("add_form", response.context)
        expected_fields = [
            "username",
            "password",
            "confirm_password",
            "role",
            "first_name",
            "last_name",
            "email",
        ]
        add_form = response.context["add_form"]
        for field_name in expected_fields:
            self.assertIn(field_name, add_form.fields)
        self.assertTrue(add_form.fields["confirm_password"].required)

        html = response.content.decode("utf-8")
        self.assertIn("<!-- Edit User & Permissions Modal -->", html)
        add_modal_html = html.split("<!-- Edit User & Permissions Modal -->")[0]
        for field_name in expected_fields:
            self.assertIn(f'id_{field_name}"', add_modal_html)

    def test_user_create_requires_matching_confirmation_password(self):
        """Creating a user requires a confirmation password that matches the password."""
        self.client.login(username="admin_user", password="password123")
        base_data = {
            "username": "dr_mismatch",
            "password": "strongpassword123",
            "first_name": "طبيب",
            "last_name": "تجريبي",
            "role": User.Role.VET,
            "is_active": "on",
        }

        # 1. Confirmation missing -> rejected
        res_missing = self.client.post(reverse("settings:user_create"), data=dict(base_data))
        self.assertEqual(res_missing.status_code, 302)
        self.assertFalse(User.objects.filter(username="dr_mismatch").exists())

        # 2. Confirmation mismatched -> rejected
        mismatch_data = dict(base_data)
        mismatch_data["confirm_password"] = "differentpassword456"
        res_mismatch = self.client.post(reverse("settings:user_create"), data=mismatch_data)
        self.assertEqual(res_mismatch.status_code, 302)
        self.assertFalse(User.objects.filter(username="dr_mismatch").exists())

        # 3. Matching confirmation -> created and audited
        ok_data = dict(base_data)
        ok_data["confirm_password"] = "strongpassword123"
        res_ok = self.client.post(reverse("settings:user_create"), data=ok_data)
        self.assertEqual(res_ok.status_code, 302)
        created = User.objects.filter(username="dr_mismatch").first()
        self.assertIsNotNone(created)
        self.assertTrue(created.check_password("strongpassword123"))
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CREATE, entity_id=str(created.pk)).exists())

    def test_user_create_ajax_returns_json_payload(self):
        """AJAX creation returns the JSON contract consumed by the add-user modal."""
        self.client.login(username="admin_user", password="password123")
        response = self.client.post(
            reverse("settings:user_create"),
            data={
                "username": "dr_ajax",
                "password": "strongpassword123",
                "confirm_password": "strongpassword123",
                "first_name": "عبر",
                "last_name": "أجاكس",
                "role": User.Role.VET,
                "is_active": "on",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["redirect_url"], reverse("settings:users"))
        self.assertTrue(User.objects.filter(username="dr_ajax").exists())

        # Invalid AJAX submission must answer 400 with field errors instead of raising an error
        bad_response = self.client.post(
            reverse("settings:user_create"),
            data={
                "username": "dr_ajax_bad",
                "password": "strongpassword123",
                "confirm_password": "differentpassword456",
                "role": User.Role.VET,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(bad_response.status_code, 400)
        self.assertFalse(bad_response.json()["success"])
        self.assertFalse(User.objects.filter(username="dr_ajax_bad").exists())

    def test_admin_updates_user_and_permissions(self):
        self.client.login(username="admin_user", password="password123")
        post_data = {
            "username": "staff_user",
            "first_name": "سامر",
            "last_name": "العلي",
            "email": "samer@clinic.local",
            "role": User.Role.STAFF,
            "is_active": "on",
            "permissions": ["can_delete"],
        }
        response = self.client.post(reverse("settings:user_update", args=[self.staff_user.pk]), data=post_data)
        self.assertEqual(response.status_code, 302)

        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.first_name, "سامر")
        self.assertTrue(self.staff_user.has_perm("accounts.can_delete"))

    def test_admin_can_change_login_username(self):
        """The admin can rename the login username of a user, not only first/last name."""
        self.client.login(username="admin_user", password="password123")
        response = self.client.post(reverse("settings:user_update", args=[self.staff_user.pk]), {
            "username": "reception_sara",
            "first_name": "سارة",
            "last_name": "الاستقبال",
            "email": "sara@clinic.local",
            "role": User.Role.STAFF,
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)

        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.username, "reception_sara")
        self.assertFalse(User.objects.filter(username__iexact="staff_user").exists())

        # The renamed account logs in with the new username and the same password
        self.assertTrue(self.client.login(username="reception_sara", password="password123"))

        # The rename is auditable
        self.assertTrue(AuditLog.objects.filter(
            action=AuditLog.Action.UPDATE,
            entity_id=str(self.staff_user.pk),
            description__contains="reception_sara",
        ).exists())

    def test_admin_can_rename_own_login_username(self):
        """Renaming the currently logged-in admin keeps the active session valid."""
        self.client.login(username="admin_user", password="password123")
        response = self.client.post(reverse("settings:user_update", args=[self.admin_user.pk]), {
            "username": "clinic_admin",
            "first_name": "المدير",
            "last_name": "العام",
            "email": "admin@clinic.local",
            "role": User.Role.ADMIN,
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)

        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.username, "clinic_admin")
        self.assertTrue(self.admin_user.is_superuser)

        # The session is bound to the user id, so the admin remains logged in after the rename
        self.assertEqual(self.client.get(reverse("settings:users")).status_code, 200)

    def test_user_update_rejects_duplicate_login_username(self):
        """A username that already belongs to another account is rejected (case-insensitive)."""
        self.client.login(username="admin_user", password="password123")
        response = self.client.post(reverse("settings:user_update", args=[self.staff_user.pk]), {
            "username": "VET_USER",
            "first_name": "سامر",
            "last_name": "العلي",
            "email": "samer@clinic.local",
            "role": User.Role.STAFF,
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.username, "staff_user")
        self.assertTrue(User.objects.filter(username="vet_user").exists())

        # Changing only the letter case of the very same account is not a duplicate
        rename_case = self.client.post(reverse("settings:user_update", args=[self.staff_user.pk]), {
            "username": "STAFF_USER",
            "first_name": "سامر",
            "last_name": "العلي",
            "email": "samer@clinic.local",
            "role": User.Role.STAFF,
            "is_active": "on",
        })
        self.assertEqual(rename_case.status_code, 302)
        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.username, "STAFF_USER")

    def test_edit_user_modal_renders_username_field(self):
        """Regression: the edit modal must expose the login username field and bind it to Alpine state."""
        self.client.login(username="admin_user", password="password123")
        response = self.client.get(reverse("settings:users"))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode("utf-8")
        self.assertIn("<!-- Edit User & Permissions Modal -->", html)
        edit_modal_html = html.split("<!-- Edit User & Permissions Modal -->", 1)[1]
        self.assertIn('name="username"', edit_modal_html)
        self.assertIn('x-model="editUsername"', edit_modal_html)

    def test_admin_resets_user_password(self):
        self.client.login(username="admin_user", password="password123")
        reset_data = {
            "new_password": "brandnewpassword456",
            "confirm_password": "brandnewpassword456",
        }
        response = self.client.post(reverse("settings:user_reset_password", args=[self.staff_user.pk]), data=reset_data)
        self.assertEqual(response.status_code, 302)

        # Verify staff can login with new password
        login_success = self.client.login(username="staff_user", password="brandnewpassword456")
        self.assertTrue(login_success)

    def test_admin_toggles_user_status(self):
        self.client.login(username="admin_user", password="password123")
        # Deactivate staff
        res = self.client.post(reverse("settings:user_toggle_status", args=[self.staff_user.pk]))
        self.assertEqual(res.status_code, 302)
        self.staff_user.refresh_from_db()
        self.assertFalse(self.staff_user.is_active)

        # Prevent admin from deactivating self
        admin_res = self.client.post(reverse("settings:user_toggle_status", args=[self.admin_user.pk]))
        self.assertEqual(admin_res.status_code, 302)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    def test_vet_visibility_with_and_without_permission(self):
        """Test that a Vet cannot see other doctors' patients or records unless granted view_all_patients, without permission conflicts."""
        dr_other = User.objects.create_user(username="dr_other", password="password123", role=User.Role.VET)
        owner = OwnerClient.objects.create(full_name="عميل تجريبي", phone="0999888777")
        animal_1 = Animal.objects.create(name="حيوان للطبيب الأول", species=Animal.Species.DOG, client=owner)
        animal_2 = Animal.objects.create(name="حيوان للطبيب الآخر", species=Animal.Species.CAT, client=owner)

        # Assign animal_1 to self.vet_user via appointment
        Appointment.objects.create(
            animal=animal_1,
            doctor=self.vet_user,
            date=timezone.localdate(),
            time=datetime.time(10, 0),
        )
        # Assign animal_2 to dr_other via medical record
        rec_other = MedicalRecord.objects.create(
            animal=animal_2,
            doctor=dr_other,
            record_type=MedicalRecord.RecordType.VISIT,
            diagnosis="تشخيص خاص بالطبيب الآخر",
        )

        # --- CASE 1: Vet WITHOUT view_all_patients ---
        self.assertFalse(can_view_all_patients(self.vet_user))
        self.assertFalse(can_view_other_doctors_records(self.vet_user))

        visible_patients_vet = get_visible_patients(self.vet_user)
        self.assertIn(animal_1, visible_patients_vet)
        self.assertNotIn(animal_2, visible_patients_vet)

        visible_records_vet = get_visible_clinical_records(self.vet_user)
        self.assertNotIn(rec_other, visible_records_vet)

        # HTTP checks: Attempting to access other doctor's patient or record returns 403
        self.client.login(username="vet_user", password="password123")
        res_patient_allowed = self.client.get(reverse("patients:detail", args=[animal_1.pk]))
        self.assertEqual(res_patient_allowed.status_code, 200)

        res_patient_forbidden = self.client.get(reverse("patients:detail", args=[animal_2.pk]))
        self.assertEqual(res_patient_forbidden.status_code, 403)

        res_record_forbidden = self.client.get(reverse("clinical:detail", args=[rec_other.pk]))
        self.assertEqual(res_record_forbidden.status_code, 403)

        # --- CASE 2: Vet WITH view_all_patients ---
        content_type = ContentType.objects.get_for_model(User)
        perm = Permission.objects.get(content_type=content_type, codename="view_all_patients")
        self.vet_user.user_permissions.add(perm)
        self.vet_user = User.objects.get(pk=self.vet_user.pk)  # Refresh permissions cache

        self.assertTrue(can_view_all_patients(self.vet_user))
        self.assertTrue(can_view_other_doctors_records(self.vet_user))

        visible_patients_after = get_visible_patients(self.vet_user)
        self.assertIn(animal_1, visible_patients_after)
        self.assertIn(animal_2, visible_patients_after)

        visible_records_after = get_visible_clinical_records(self.vet_user)
        self.assertIn(rec_other, visible_records_after)

        # HTTP checks: Now has permission to view other doctor's patient and record
        res_patient_now_ok = self.client.get(reverse("patients:detail", args=[animal_2.pk]))
        self.assertEqual(res_patient_now_ok.status_code, 200)

        res_record_now_ok = self.client.get(reverse("clinical:detail", args=[rec_other.pk]))
        self.assertIn(res_record_now_ok.status_code, [200, 302])

        # --- CASE 3: Admin & Staff (Conflict-Free: never blocked from clinic patients) ---
        visible_patients_admin = get_visible_patients(self.admin_user)
        self.assertIn(animal_1, visible_patients_admin)
        self.assertIn(animal_2, visible_patients_admin)

        visible_patients_staff = get_visible_patients(self.staff_user)
        self.assertIn(animal_1, visible_patients_staff)
        self.assertIn(animal_2, visible_patients_staff)

    def test_login_page_shows_forgot_password(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نسيت كلمة المرور؟")
        self.assertContains(response, reverse("accounts:password_reset"))

    def test_offline_password_reset_with_recovery_code(self):
        from apps.accounts.services import issue_new_recovery_code, normalize_recovery_code
        from apps.accounts.models import PasswordRecoverySettings

        code = issue_new_recovery_code()
        response = self.client.post(reverse("accounts:password_reset"), {
            "username": "admin_user",
            "recovery_code": code.lower(),
            "new_password": "newAdminPass9",
            "confirm_password": "newAdminPass9",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تم تعيين كلمة المرور الجديدة بنجاح")
        self.assertTrue(self.client.login(username="admin_user", password="newAdminPass9"))
        cfg = PasswordRecoverySettings.get_settings()
        self.assertEqual(normalize_recovery_code(code).count("-"), 2)

    def test_offline_password_reset_rejects_wrong_code(self):
        from apps.accounts.services import issue_new_recovery_code

        issue_new_recovery_code()
        response = self.client.post(reverse("accounts:password_reset"), {
            "username": "admin_user",
            "recovery_code": "PC-AAAA-BBBB",
            "new_password": "newAdminPass9",
            "confirm_password": "newAdminPass9",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "غير صحيح")
        self.assertTrue(self.client.login(username="admin_user", password="password123"))

    def test_non_admin_cannot_regenerate_recovery_code(self):
        self.client.login(username="staff_user", password="password123")
        response = self.client.post(reverse("accounts:regenerate_recovery_code"))
        self.assertEqual(response.status_code, 403)

    def test_admin_login_issues_recovery_code_when_missing(self):
        from apps.accounts.models import PasswordRecoverySettings
        from apps.accounts.services import SESSION_RECOVERY_CODE_KEY

        PasswordRecoverySettings.objects.all().delete()
        response = self.client.post(reverse("accounts:login"), {
            "username": "admin_user",
            "password": "password123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:recovery_code"))
        session = self.client.session
        self.assertTrue(session.get(SESSION_RECOVERY_CODE_KEY, "").startswith("PC-"))

    def test_delete_permission_enforced_strictly(self):
        """A user without can_delete permission is rejected with 403 Forbidden on delete requests."""
        owner = OwnerClient.objects.create(full_name="عميل للحذف", phone="0999111222")
        animal = Animal.objects.create(name="حيوان اختبار", species=Animal.Species.DOG, client=owner)

        # Login as staff (who does not have can_delete)
        self.client.login(username="staff_user", password="password123")

        # Attempt to delete patient
        res = self.client.post(reverse("patients:delete", args=[animal.pk]))
        self.assertEqual(res.status_code, 403)
        self.assertContains(res, "403", status_code=403)
        animal.refresh_from_db()
        self.assertFalse(animal.is_deleted)  # Record was NOT deleted!

        # Attempt to delete client
        client_res = self.client.post(reverse("clients:delete", args=[owner.pk]))
        self.assertEqual(client_res.status_code, 403)
        owner.refresh_from_db()
        self.assertFalse(owner.is_deleted)  # Record was NOT deleted!

    def test_browsing_allowed_for_all_authenticated_users(self):
        """Any authenticated user can browse main list pages."""
        self.client.login(username="staff_user", password="password123")

        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("clients:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("patients:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("appointments:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("clinical:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reminders:list")).status_code, 200)

    def test_mutating_actions_require_individual_permissions(self):
        """Staff can create clients and appointments as their core role, but cannot edit clinical records or view reports without explicit permissions."""
        self.client.login(username="staff_user", password="password123")

        # Staff CAN create client (core role)
        res_client = self.client.post(reverse("clients:create"), {"full_name": "عميل تجريبي جديد", "phone": "0999000111"})
        self.assertEqual(res_client.status_code, 302)

        # Staff CANNOT create clinical record without can_edit_clinical -> 403
        res_clin = self.client.post(reverse("clinical:create"), {"diagnosis": "ممنوع"})
        self.assertEqual(res_clin.status_code, 403)

        # Staff CANNOT access reports without can_view_reports -> 403
        res_reports = self.client.get(reverse("reports:reports"))
        self.assertEqual(res_reports.status_code, 403)

    def test_core_permissions_automatically_enforced_on_creation(self):
        """Creating a user with a role automatically enforces their core permissions."""
        self.client.login(username="admin_user", password="password123")
        res = self.client.post(reverse("settings:user_create"), {
            "username": "dr_auto_core",
            "password": "password123",
            "confirm_password": "password123",
            "first_name": "طبيب",
            "last_name": "أساسي",
            "role": User.Role.VET,
            "is_active": "on",
            "permissions": [],  # Admin selected nothing!
        })
        self.assertEqual(res.status_code, 302)
        new_vet = User.objects.get(username="dr_auto_core")
        self.assertTrue(new_vet.has_perm("accounts.can_edit_clinical"))

    def test_deactivated_user_cannot_perform_actions(self):
        """When admin deactivates a user account, the user cannot log in or perform any actions."""
        self.vet_user.is_active = False
        self.vet_user.save()

        # Login is rejected
        login_result = self.client.login(username="vet_user", password="password123")
        self.assertFalse(login_result)

    def test_cannot_deactivate_or_demote_last_active_admin(self):
        """UserEditForm and toggle status must prevent deactivating/demoting the sole active admin."""
        # Ensure only 1 active admin exists
        User.objects.filter(role=User.Role.ADMIN).exclude(pk=self.admin_user.pk).delete()

        # Try to demote the sole active admin to STAFF via UserEditForm
        from apps.accounts.forms import UserEditForm
        form = UserEditForm(
            data={
                "first_name": "Sole",
                "last_name": "Admin",
                "email": "admin@clinic.local",
                "role": User.Role.STAFF,
                "is_active": True,
            },
            instance=self.admin_user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("المدير النشط الوحيد", str(form.errors))


