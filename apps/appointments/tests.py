import datetime
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.clients.models import Client
from apps.patients.models import Animal
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog


class AppointmentsBusinessRulesAndViewsTests(TestCase):
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
        self.vet_dr_sara = User.objects.create_user(
            username="dr_sara",
            password="password123",
            first_name="سارة",
            last_name="محمود",
            role=User.Role.VET,
        )

        self.client_runner.login(username="admin_user", password="password123")

        # Owner and Animals
        self.owner = Client.objects.create(
            full_name="هاني منصور",
            phone="0911223344",
            address="دمشق - أبو رمانة",
        )
        self.patient_1 = Animal.objects.create(
            name="لونا",
            species=Animal.Species.CAT,
            client=self.owner,
        )
        self.patient_2 = Animal.objects.create(
            name="ماكس",
            species=Animal.Species.DOG,
            client=self.owner,
        )

        from django.utils import timezone
        self.test_date = timezone.localdate() + datetime.timedelta(days=1)

    def test_appointment_creation_and_audit_log(self):
        post_data = {
            "animal": str(self.patient_1.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "date": self.test_date.strftime("%Y-%m-%d"),
            "time": "10:00",
            "duration": "30",
            "appointment_type": Appointment.AppointmentType.CHECKUP,
            "status": Appointment.Status.SCHEDULED,
            "brought_by": "أحمد (أخ المالك)",
            "notes": "فحص دوري أولي",
        }
        response = self.client_runner.post(reverse("appointments:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        appt = Appointment.objects.filter(animal=self.patient_1, date=self.test_date).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.doctor, self.vet_dr_ali)
        self.assertEqual(appt.created_by, self.admin_user)
        self.assertEqual(appt.brought_by, "أحمد (أخ المالك)")

        # Verify Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                entity_id=str(appt.pk),
            ).exists()
        )

    def test_appointment_conflict_rule_same_vet_rejection(self):
        """A Vet cannot have overlapping appointments."""
        # Create first appointment from 10:00 to 10:30 (30 mins) for Dr. Ali
        Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(10, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        # Attempt to create an overlapping appointment for Dr. Ali at 10:15 (conflict!)
        overlapping_appt = Appointment(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(10, 15),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        with self.assertRaises(ValidationError):
            overlapping_appt.full_clean()

    def test_appointment_concurrent_different_vets_allowed(self):
        """Different Vets can have appointments at the exact same date and time."""
        # Appointment for Dr. Ali at 10:00 (30 mins)
        appt1 = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(10, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        # Appointment for Dr. Sara at 10:00 (30 mins) -> Should NOT conflict
        appt2 = Appointment.objects.create(
            animal=self.patient_2,
            doctor=self.vet_dr_sara,
            date=self.test_date,
            time=datetime.time(10, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        self.assertIsNotNone(appt1.pk)
        self.assertIsNotNone(appt2.pk)

    def test_cancelled_or_deleted_appointment_does_not_conflict(self):
        """Cancelled or deleted appointments do not block booking the same time slot."""
        # Create a cancelled appointment for Dr. Ali at 11:00
        Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(11, 0),
            duration=30,
            status=Appointment.Status.CANCELLED,
        )

        # New active appointment for Dr. Ali at 11:00 should succeed
        new_appt = Appointment.objects.create(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(11, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )
        self.assertIsNotNone(new_appt.pk)

    def test_appointment_status_update(self):
        appt = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(14, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        response = self.client_runner.post(
            reverse("appointments:update_status", args=[appt.pk]),
            data={"status": Appointment.Status.COMPLETED},
        )
        self.assertEqual(response.status_code, 302)

        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)

        # Verify Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                entity_id=str(appt.pk),
            ).exists()
        )

    def test_appointment_soft_delete_and_restore(self):
        appt = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(16, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        # Delete
        del_res = self.client_runner.post(reverse("appointments:delete", args=[appt.pk]))
        self.assertEqual(del_res.status_code, 302)

        appt.refresh_from_db()
        self.assertTrue(appt.is_deleted)
        self.assertFalse(Appointment.objects.alive().filter(pk=appt.pk).exists())

        # Restore
        restore_res = self.client_runner.post(reverse("appointments:restore", args=[appt.pk]))
        self.assertEqual(restore_res.status_code, 302)

        appt.refresh_from_db()
        self.assertFalse(appt.is_deleted)

    def test_fullcalendar_api_endpoint(self):
        Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(9, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        start_iso = f"{self.test_date.strftime('%Y-%m-%d')}T00:00:00"
        end_iso = f"{(self.test_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}T00:00:00"
        response = self.client_runner.get(
            reverse("appointments:api_events"),
            {"start": start_iso, "end": end_iso},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["extendedProps"]["animal_name"], "لونا")
        self.assertIn("backgroundColor", data[0])

    def test_appointment_conflict_matrix_rules(self):
        """
        Verify the confirmed Conflict Rules:
        - Rule A: Two BATH appointments must NEVER overlap in time, regardless of doctor.
        - Rule B: Same-doctor overlap is disallowed for ALL type combinations (including Treatment + Bath).
        - Different doctors CAN overlap for non-BATH (or at most one BATH).
        """
        # Base appointment: Treatment at 15:00-15:30 with Dr. Ali
        treatment_appt = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(15, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.TREATMENT,
            status=Appointment.Status.SCHEDULED,
        )

        # 1. Rule B: Bath concurrent with Treatment for the SAME doctor -> CONFLICT
        bath_same_doc = Appointment(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(15, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.BATH,
            status=Appointment.Status.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            bath_same_doc.full_clean()

        # 2. Bath concurrent with Treatment for a DIFFERENT doctor -> ALLOWED
        bath_diff_doc = Appointment(
            animal=self.patient_2,
            doctor=self.vet_dr_sara,
            date=self.test_date,
            time=datetime.time(15, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.BATH,
            status=Appointment.Status.SCHEDULED,
        )
        bath_diff_doc.full_clean()  # Should NOT raise
        bath_diff_doc.save()
        self.assertIsNotNone(bath_diff_doc.pk)

        # 3. Rule A: Another Bath concurrent with existing Bath (even with different doctor Dr. Ali) -> CONFLICT
        bath_overlap_diff_doc = Appointment(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(15, 10),
            duration=30,
            appointment_type=Appointment.AppointmentType.BATH,
            status=Appointment.Status.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            bath_overlap_diff_doc.full_clean()

        # 2. Surgery concurrent with Treatment -> CONFLICT
        surgery_appt = Appointment(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(15, 10),
            duration=30,
            appointment_type=Appointment.AppointmentType.SURGERY,
            status=Appointment.Status.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            surgery_appt.full_clean()

        # 3. Grooming concurrent with Treatment -> CONFLICT
        grooming_appt = Appointment(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(15, 15),
            duration=30,
            appointment_type=Appointment.AppointmentType.GROOMING,
            status=Appointment.Status.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            grooming_appt.full_clean()

        # 4. Check-up concurrent with Treatment -> CONFLICT
        checkup_appt = Appointment(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(15, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.CHECKUP,
            status=Appointment.Status.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            checkup_appt.full_clean()

        # 5. Grooming concurrent with Checkup -> CONFLICT
        checkup_base = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_sara,
            date=self.test_date,
            time=datetime.time(17, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.CHECKUP,
            status=Appointment.Status.SCHEDULED,
        )
        grooming_checkup = Appointment(
            animal=self.patient_2,
            doctor=self.vet_dr_sara,
            date=self.test_date,
            time=datetime.time(17, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.GROOMING,
            status=Appointment.Status.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            grooming_checkup.full_clean()

    def test_appointment_date_range_filtering(self):
        """Test appointments list filtering with from_date and to_date."""
        Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=datetime.date(2026, 9, 10),
            time=datetime.time(10, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )
        Appointment.objects.create(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=datetime.date(2026, 9, 20),
            time=datetime.time(10, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        # Range filtering: 2026-09-05 to 2026-09-15 (only first appt)
        res = self.client_runner.get(reverse("appointments:list"), {
            "from_date": "2026-09-05",
            "to_date": "2026-09-15"
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "2026-09-10")
        self.assertNotContains(res, "2026-09-20")
        appts = res.context["appointments"]
        self.assertEqual(len(appts), 1)
        self.assertEqual(appts[0].animal, self.patient_1)

    def test_database_exclusion_constraints_enforced(self):
        """Verify PostgreSQL ExclusionConstraints raise IntegrityError when bypassing Python validation."""
        from django.db import IntegrityError, connection
        if connection.vendor != 'postgresql':
            self.skipTest("PostgreSQL exclusion constraints require PostgreSQL database.")

        # 1. Test Doctor Overlap at DB level
        Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(11, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.CHECKUP,
            status=Appointment.Status.SCHEDULED,
        )

        with self.assertRaises(IntegrityError):
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO appointments_appointment (
                        created_at, updated_at, is_deleted, date, time, duration,
                        appointment_type, status, brought_by, notes,
                        animal_id, doctor_id
                    ) VALUES (
                        NOW(), NOW(), false, %s, '11:15', 30,
                        'TREATMENT', 'SCHEDULED', '', '',
                        %s, %s
                    )
                    """,
                    [self.test_date, self.patient_2.pk, self.vet_dr_ali.pk]
                )

        # 2. Test Bath Overlap at DB level across different doctors
        Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(13, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.BATH,
            status=Appointment.Status.SCHEDULED,
        )

        with self.assertRaises(IntegrityError):
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO appointments_appointment (
                        created_at, updated_at, is_deleted, date, time, duration,
                        appointment_type, status, brought_by, notes,
                        animal_id, doctor_id
                    ) VALUES (
                        NOW(), NOW(), false, %s, '13:15', 30,
                        'BATH', 'SCHEDULED', '', '',
                        %s, %s
                    )
                    """,
                    [self.test_date, self.patient_2.pk, self.vet_dr_sara.pk]
                )

        # 3. Test Animal Overlap at DB level across different doctors
        Appointment.objects.create(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(16, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.CHECKUP,
            status=Appointment.Status.SCHEDULED,
        )

        with self.assertRaises(IntegrityError):
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO appointments_appointment (
                        created_at, updated_at, is_deleted, date, time, duration,
                        appointment_type, status, brought_by, notes,
                        animal_id, doctor_id
                    ) VALUES (
                        NOW(), NOW(), false, %s, '16:15', 30,
                        'TREATMENT', 'SCHEDULED', '', '',
                        %s, %s
                    )
                    """,
                    [self.test_date, self.patient_2.pk, self.vet_dr_sara.pk]
                )

    def test_appointment_status_reactivation_conflict_handling(self):
        """Reactivating a cancelled appointment that now overlaps another active appointment is gracefully rejected."""
        # 1. Active appointment at 10:00 - 10:30
        appt_active = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(10, 0),
            duration=30,
            appointment_type=Appointment.AppointmentType.CHECKUP,
            status=Appointment.Status.SCHEDULED,
        )

        # 2. Cancelled appointment at 10:15 - 10:45 with same doctor
        appt_cancelled = Appointment.objects.create(
            animal=self.patient_2,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(10, 15),
            duration=30,
            appointment_type=Appointment.AppointmentType.TREATMENT,
            status=Appointment.Status.CANCELLED,
        )

        # 3. Attempt status update to SCHEDULED via view
        resp = self.client_runner.post(
            reverse("appointments:update_status", args=[appt_cancelled.pk]),
            data={"status": Appointment.Status.SCHEDULED},
        )
        self.assertEqual(resp.status_code, 302)
        appt_cancelled.refresh_from_db()
        self.assertEqual(appt_cancelled.status, Appointment.Status.CANCELLED)

        # 4. Attempt status update via AJAX
        resp_ajax = self.client_runner.post(
            reverse("appointments:update_status", args=[appt_cancelled.pk]),
            data={"status": Appointment.Status.SCHEDULED},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp_ajax.status_code, 400)
        data = resp_ajax.json()
        self.assertFalse(data["success"])
        self.assertIn("تضارب", data["error"])

    def test_reminder_reset_on_appointment_cancelled_or_deleted(self):
        """When a converted appointment is cancelled, soft-deleted, or hard-deleted, the linked reminder reverts to PENDING."""
        from apps.reminders.models import Reminder

        # A. Cancellation via status update
        appt1 = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(9, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )
        rem1 = Reminder.objects.create(
            animal=self.patient_1,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=self.test_date,
            status=Reminder.Status.CONVERTED,
            converted_appointment=appt1,
        )

        # Cancel appt1
        self.client_runner.post(
            reverse("appointments:update_status", args=[appt1.pk]),
            data={"status": Appointment.Status.CANCELLED},
        )
        rem1.refresh_from_db()
        self.assertEqual(rem1.status, Reminder.Status.PENDING)
        self.assertIsNone(rem1.converted_appointment)

        # B. Soft-delete of appointment
        appt2 = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(11, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )
        rem2 = Reminder.objects.create(
            animal=self.patient_1,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=self.test_date,
            status=Reminder.Status.CONVERTED,
            converted_appointment=appt2,
        )

        appt2.soft_delete()
        rem2.refresh_from_db()
        self.assertEqual(rem2.status, Reminder.Status.PENDING)
        self.assertIsNone(rem2.converted_appointment)

        # C. Hard-delete of appointment
        appt3 = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(12, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )
        rem3 = Reminder.objects.create(
            animal=self.patient_1,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=self.test_date,
            status=Reminder.Status.CONVERTED,
            converted_appointment=appt3,
        )

        appt3.delete()
        rem3.refresh_from_db()
        self.assertEqual(rem3.status, Reminder.Status.PENDING)
        self.assertIsNone(rem3.converted_appointment)

    def test_appointment_past_date_warning_and_override(self):
        """Creating an appointment in the past triggers a warning and requires confirmation."""
        from django.utils import timezone
        past_date = timezone.localdate() - datetime.timedelta(days=3)

        post_data = {
            "animal": str(self.patient_1.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "date": past_date.strftime("%Y-%m-%d"),
            "time": "10:00",
            "duration": "30",
            "appointment_type": Appointment.AppointmentType.CHECKUP,
            "status": Appointment.Status.SCHEDULED,
        }

        # 1. First attempt without confirmation -> rejected
        res1 = self.client_runner.post(reverse("appointments:create"), data=post_data)
        self.assertEqual(res1.status_code, 302)
        self.assertFalse(Appointment.objects.filter(animal=self.patient_1, date=past_date).exists())

        # 2. Resubmit with confirm_past_date=1 -> succeeds
        post_data_confirmed = post_data.copy()
        post_data_confirmed["confirm_past_date"] = "1"
        res2 = self.client_runner.post(reverse("appointments:create"), data=post_data_confirmed)
        self.assertEqual(res2.status_code, 302)
        self.assertTrue(Appointment.objects.filter(animal=self.patient_1, date=past_date).exists())

    def test_appointment_filtering_by_type_and_vaccine(self):
        """Test appointments list view filtering by appointment_type and vaccine_name."""
        appt_checkup = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(10, 0),
            appointment_type=Appointment.AppointmentType.CHECKUP,
        )
        appt_vac1 = Appointment.objects.create(
            animal=self.patient_1,
            doctor=self.vet_dr_ali,
            date=self.test_date,
            time=datetime.time(11, 0),
            appointment_type=Appointment.AppointmentType.VACCINATION,
            vaccine_name="تطعيم رباعي للقطط",
        )
        appt_vac2 = Appointment.objects.create(
            animal=self.patient_2,
            doctor=self.vet_dr_sara,
            date=self.test_date,
            time=datetime.time(12, 0),
            appointment_type=Appointment.AppointmentType.VACCINATION,
            vaccine_name="لقاح السعار",
        )

        # 1. Filter by appointment_type = VACCINATION
        res = self.client_runner.get(reverse("appointments:list"), {"appointment_type": "VACCINATION"})
        self.assertEqual(res.status_code, 200)
        appts = list(res.context["appointments"])
        self.assertIn(appt_vac1, appts)
        self.assertIn(appt_vac2, appts)
        self.assertNotIn(appt_checkup, appts)

        # 2. Filter by appointment_type = VACCINATION and vaccine_name = تطعيم رباعي للقطط
        res2 = self.client_runner.get(reverse("appointments:list"), {
            "appointment_type": "VACCINATION",
            "vaccine_name": "تطعيم رباعي للقطط",
        })
        self.assertEqual(res2.status_code, 200)
        appts2 = list(res2.context["appointments"])
        self.assertIn(appt_vac1, appts2)
        self.assertNotIn(appt_vac2, appts2)
        self.assertNotIn(appt_checkup, appts2)





