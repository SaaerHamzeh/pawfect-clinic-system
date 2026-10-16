import datetime
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from apps.clients.models import Client
from apps.patients.models import Animal
from apps.appointments.models import Appointment
from apps.reminders.models import Reminder
from apps.audit.models import AuditLog


class RemindersBusinessRulesAndViewsTests(TestCase):
    def setUp(self):
        self.client_runner = TestClient()

        # Users
        self.admin_user = User.objects.create_superuser(
            username="admin_user",
            password="password123",
            role=User.Role.ADMIN,
        )
        self.vet_dr_ali = User.objects.create_user(
            username="dr_ali",
            password="password123",
            first_name="علي",
            last_name="الأحمد",
            role=User.Role.VET,
        )

        self.client_runner.login(username="admin_user", password="password123")

        # Owner and Animal
        self.owner = Client.objects.create(
            full_name="فراس خوري",
            phone="0955667788",
            address="دمشق - المزة",
        )
        self.patient = Animal.objects.create(
            name="روكي",
            species=Animal.Species.DOG,
            client=self.owner,
        )

        self.due_date = timezone.localdate() + datetime.timedelta(days=7)

    def test_reminder_creation_and_audit_log(self):
        post_data = {
            "animal": str(self.patient.pk),
            "reminder_type": Reminder.ReminderType.VACCINATION,
            "due_date": self.due_date.strftime("%Y-%m-%d"),
            "status": Reminder.Status.PENDING,
            "notes": "الجرعة السنوية للرباعي",
        }
        response = self.client_runner.post(reverse("reminders:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        rem = Reminder.objects.filter(animal=self.patient, due_date=self.due_date).first()
        self.assertIsNotNone(rem)
        self.assertEqual(rem.reminder_type, Reminder.ReminderType.VACCINATION)
        self.assertEqual(rem.status, Reminder.Status.PENDING)

        # Audit Log Check
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                entity_id=str(rem.pk),
            ).exists()
        )

    def test_reminder_convert_to_appointment(self):
        """Converting a pending reminder creates an appointment and sets reminder status to CONVERTED."""
        rem = Reminder.objects.create(
            animal=self.patient,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=self.due_date,
            status=Reminder.Status.PENDING,
            notes="فحص أسنان دوري",
        )

        convert_data = {
            "doctor": str(self.vet_dr_ali.pk),
            "date": self.due_date.strftime("%Y-%m-%d"),
            "time": "11:00",
            "duration": "30",
            "brought_by": "فراس خوري",
            "notes": "فحص أسنان دوري",
        }

        response = self.client_runner.post(
            reverse("reminders:convert", args=[rem.pk]),
            data=convert_data,
        )
        self.assertEqual(response.status_code, 302)

        rem.refresh_from_db()
        self.assertEqual(rem.status, Reminder.Status.CONVERTED)
        self.assertIsNotNone(rem.converted_appointment)

        # Verify created appointment
        appt = rem.converted_appointment
        self.assertEqual(appt.animal, self.patient)
        self.assertEqual(appt.doctor, self.vet_dr_ali)
        self.assertEqual(appt.date, self.due_date)
        self.assertEqual(appt.time, datetime.time(11, 0))
        self.assertEqual(appt.status, Appointment.Status.SCHEDULED)

        # Verify Audit Logs for both
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.CREATE, entity_id=str(appt.pk)).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.UPDATE, entity_id=str(rem.pk)).exists()
        )

    def test_reminder_from_clinical_visit_auto_assigns_doctor_on_conversion(self):
        """Converting a reminder generated from a doctor's visit automatically assigns that doctor to the new appointment."""
        from apps.clinical.models import MedicalRecord

        vet_dr_sara = User.objects.create_user(
            username="dr_sara_rem",
            password="password123",
            first_name="سارة",
            role=User.Role.VET,
        )

        record = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=vet_dr_sara,
            diagnosis="متابعة حالة خاصة",
        )

        rem = Reminder.objects.create(
            animal=self.patient,
            medical_record=record,
            reminder_type=Reminder.ReminderType.FOLLOW_UP,
            due_date=self.due_date,
            status=Reminder.Status.PENDING,
            notes="متابعة د. سارة",
        )

        self.assertEqual(rem.assigned_doctor, vet_dr_sara)

        # Even if another doctor ID was sent in form POST (e.g. Dr. Ali), backend automatically enforces Dr. Sara
        convert_data = {
            "doctor": str(self.vet_dr_ali.pk),
            "date": self.due_date.strftime("%Y-%m-%d"),
            "time": "14:00",
            "duration": "30",
        }

        response = self.client_runner.post(
            reverse("reminders:convert", args=[rem.pk]),
            data=convert_data,
        )
        self.assertEqual(response.status_code, 302)

        rem.refresh_from_db()
        self.assertEqual(rem.status, Reminder.Status.CONVERTED)
        self.assertIsNotNone(rem.converted_appointment)
        self.assertEqual(rem.converted_appointment.doctor, vet_dr_sara)

    def test_cannot_convert_non_pending_reminder(self):
        rem = Reminder.objects.create(
            animal=self.patient,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=self.due_date,
            status=Reminder.Status.CANCELLED,
        )
        convert_data = {
            "doctor": str(self.vet_dr_ali.pk),
            "date": self.due_date.strftime("%Y-%m-%d"),
            "time": "12:00",
            "duration": "30",
        }
        response = self.client_runner.post(
            reverse("reminders:convert", args=[rem.pk]),
            data=convert_data,
        )
        self.assertEqual(response.status_code, 302)
        rem.refresh_from_db()
        self.assertIsNone(rem.converted_appointment)

    def test_reminder_status_update(self):
        rem = Reminder.objects.create(
            animal=self.patient,
            reminder_type=Reminder.ReminderType.MEDICATION,
            due_date=self.due_date,
            status=Reminder.Status.PENDING,
        )

        response = self.client_runner.post(
            reverse("reminders:update_status", args=[rem.pk]),
            data={"status": Reminder.Status.COMPLETED},
        )
        self.assertEqual(response.status_code, 302)

        rem.refresh_from_db()
        self.assertEqual(rem.status, Reminder.Status.COMPLETED)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                entity_id=str(rem.pk),
            ).exists()
        )

    def test_reminder_soft_delete_and_restore(self):
        rem = Reminder.objects.create(
            animal=self.patient,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=self.due_date,
            status=Reminder.Status.PENDING,
        )

        # Delete
        del_res = self.client_runner.post(reverse("reminders:delete", args=[rem.pk]))
        self.assertEqual(del_res.status_code, 302)

        rem.refresh_from_db()
        self.assertTrue(rem.is_deleted)
        self.assertFalse(Reminder.objects.alive().filter(pk=rem.pk).exists())

        # Restore
        restore_res = self.client_runner.post(reverse("reminders:restore", args=[rem.pk]))
        self.assertEqual(restore_res.status_code, 302)

        rem.refresh_from_db()
        self.assertFalse(rem.is_deleted)

    def test_reminders_filters_and_views(self):
        # Create overdue reminder
        Reminder.objects.create(
            animal=self.patient,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=timezone.localdate() - datetime.timedelta(days=2),
            status=Reminder.Status.PENDING,
            notes="فحص متأخر",
        )

        # Filter overdue
        response = self.client_runner.get(reverse("reminders:list"), {"due": "overdue"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فحص متأخر")

    def test_reminder_update_view(self):
        """Test editing reminder details and status via update view."""
        rem = Reminder.objects.create(
            animal=self.patient,
            reminder_type=Reminder.ReminderType.GENERAL,
            due_date=self.due_date,
            status=Reminder.Status.PENDING,
            notes="تذكير مبدئي",
        )
        new_due = self.due_date + datetime.timedelta(days=5)
        update_data = {
            "reminder_type": "CHECKUP",
            "due_date": new_due.strftime("%Y-%m-%d"),
            "status": "COMPLETED",
            "notes": "تم إنجاز التذكير",
        }
        res = self.client_runner.post(reverse("reminders:update", args=[rem.pk]), data=update_data)
        self.assertEqual(res.status_code, 302)

        rem.refresh_from_db()
        self.assertEqual(rem.reminder_type, Reminder.ReminderType.CHECKUP)
        self.assertEqual(rem.due_date, new_due)
        self.assertEqual(rem.status, Reminder.Status.COMPLETED)
        self.assertEqual(rem.notes, "تم إنجاز التذكير")

    def test_reminder_date_range_filtering(self):
        """Test reminders date range filtering with from_date and to_date."""
        rem1 = Reminder.objects.create(
            animal=self.patient,
            due_date=datetime.date(2026, 10, 5),
            status=Reminder.Status.PENDING,
            notes="تذكير أول الشهر",
        )
        rem2 = Reminder.objects.create(
            animal=self.patient,
            due_date=datetime.date(2026, 10, 25),
            status=Reminder.Status.PENDING,
            notes="تذكير آخر الشهر",
        )

        # Filter range: 2026-10-01 to 2026-10-10 (only rem1)
        res = self.client_runner.get(reverse("reminders:list"), {
            "from_date": "2026-10-01",
            "to_date": "2026-10-10"
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "تذكير أول الشهر")
        self.assertNotContains(res, "تذكير آخر الشهر")

    def test_reminder_alphabetical_sorting(self):
        """Test reminders sorting alphabetically by animal name and client name."""
        client_b = Client.objects.create(full_name="أحمد يوسف", phone="0911002200")
        patient_b = Animal.objects.create(name="أوسكار", species=Animal.Species.CAT, client=client_b)

        client_c = Client.objects.create(full_name="مازن سعيد", phone="0911003300")
        patient_c = Animal.objects.create(name="بسبس", species=Animal.Species.CAT, client=client_c)

        rem_b = Reminder.objects.create(animal=patient_b, due_date=self.due_date, status=Reminder.Status.PENDING)
        rem_c = Reminder.objects.create(animal=patient_c, due_date=self.due_date, status=Reminder.Status.PENDING)

        # 1. Sort by animal name ascending (أوسكار ثم بسبس)
        res_asc = self.client_runner.get(reverse("reminders:list"), {"sort": "animal_asc"})
        self.assertEqual(res_asc.status_code, 200)
        rem_list = list(res_asc.context["reminders"])
        index_b = rem_list.index(rem_b)
        index_c = rem_list.index(rem_c)
        self.assertLess(index_b, index_c)

        # 2. Sort by client name ascending ("أحمد يوسف" ثم "مازن سعيد")
        res_client = self.client_runner.get(reverse("reminders:list"), {"sort": "client_asc"})
        self.assertEqual(res_client.status_code, 200)
        rem_list_client = list(res_client.context["reminders"])
        index_b_client = rem_list_client.index(rem_b)
        index_c_client = rem_list_client.index(rem_c)
        self.assertLess(index_b_client, index_c_client)

    def test_reminder_actions_visibility_respects_permissions(self):
        """Ensure convert-to-appointment and edit reminder buttons only appear when user has can_manage_appointments."""
        rem = Reminder.objects.create(
            animal=self.patient,
            due_date=self.due_date,
            status=Reminder.Status.PENDING,
            notes="فحص دوري للتجربة"
        )
        # 1. Admin has permission -> sees "تحويل لموعد" and "تعديل التذكير"
        res_admin = self.client_runner.get(reverse("reminders:list"))
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, "تحويل لموعد")
        self.assertContains(res_admin, "تعديل التذكير")

        res_patient_admin = self.client_runner.get(reverse("patients:detail", args=[self.patient.pk]))
        self.assertEqual(res_patient_admin.status_code, 200)
        self.assertContains(res_patient_admin, "تحويل لموعد")

        # 2. Staff user has can_manage_appointments as core role -> sees "تحويل لموعد"
        staff_user = User.objects.create_user(
            username="staff_core",
            password="password123",
            role=User.Role.STAFF,
        )
        client_staff = TestClient()
        client_staff.login(username="staff_core", password="password123")
        res_staff = client_staff.get(reverse("reminders:list"))
        self.assertEqual(res_staff.status_code, 200)
        self.assertContains(res_staff, "تحويل لموعد")

        # 3. Vet user with view_all_patients but without can_manage_appointments -> does NOT see "تحويل لموعد" or "تعديل التذكير"
        vet_user = User.objects.create_user(
            username="vet_no_appt",
            password="password123",
            role=User.Role.VET,
        )
        ct = ContentType.objects.get_for_model(User)
        perm = Permission.objects.get(content_type=ct, codename="view_all_patients")
        vet_user.user_permissions.add(perm)
        client_vet = TestClient()
        client_vet.login(username="vet_no_appt", password="password123")

        res_vet = client_vet.get(reverse("reminders:list"))
        self.assertEqual(res_vet.status_code, 200)
        self.assertNotContains(res_vet, "تحويل لموعد")
        self.assertNotContains(res_vet, "تعديل التذكير")

        res_patient_vet = client_vet.get(reverse("patients:detail", args=[self.patient.pk]))
        self.assertEqual(res_patient_vet.status_code, 200)
        self.assertNotContains(res_patient_vet, "تحويل لموعد")
        self.assertNotContains(res_patient_vet, "إدارة التذكيرات في القائمة العامة")

