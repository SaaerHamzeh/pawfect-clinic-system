import datetime
from django.test import TestCase, Client as HttpClient
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse

from apps.core.validators import validate_phone_number
from apps.clients.models import Client
from apps.patients.models import Animal
from apps.appointments.models import Appointment
from apps.reminders.models import Reminder
from apps.clinical.models import MedicalRecord

User = get_user_model()


class CoreEnhancementsAndBusinessRulesTests(TestCase):
    """Tests for recent clinic enhancements: phone rules, working hours, hard-delete, and status sync."""

    def setUp(self):
        # Admin user with full permissions
        self.admin = User.objects.create_superuser(
            username="admin_test",
            email="admin@pawfect.local",
            password="adminpassword123",
        )
        self.client_http = HttpClient()
        self.client_http.force_login(self.admin)

        # Standard client & patient for testing
        self.test_client = Client.objects.create(
            full_name="طارق العلي",
            phone="0933112233",
            address="دمشق - المزة",
        )
        self.test_patient = Animal.objects.create(
            name="بيسو",
            species=Animal.Species.CAT,
            client=self.test_client,
            gender=Animal.Gender.MALE,
        )

    # 1. Syrian and International Phone Validation Tests
    def test_syrian_phone_valid_formats(self):
        """Test valid Syrian numbers (10 digits starting with 09, or Syrian international codes)."""
        valid_numbers = [
            "0933123456",
            "0944987654",
            "0988112233",
            "0999000111",
            "+963933123456",
            "00963944987654",
            "+963 933 123 456",
        ]
        for num in valid_numbers:
            try:
                validate_phone_number(num)
            except ValidationError:
                self.fail(f"Phone validator failed unexpectedly for valid number: {num}")

    def test_international_phone_valid_formats(self):
        """Test valid non-Syrian international phone numbers (must have + or 00 country prefix)."""
        valid_international = [
            "+96170123456",     # Lebanon
            "+962791234567",    # Jordan
            "+971501234567",    # UAE
            "+12025550123",     # US
            "00966501234567",   # Saudi Arabia with 00
        ]
        for num in valid_international:
            try:
                validate_phone_number(num)
            except ValidationError:
                self.fail(f"Phone validator failed for valid international number: {num}")

    def test_syrian_phone_invalid_formats(self):
        """Test invalid Syrian numbers (wrong length, not starting with 09, missing country code)."""
        invalid_numbers = [
            "0833123456",    # Doesn't start with 09
            "093312345",     # 9 digits (too short)
            "09331234567",   # 11 digits (too long)
            "0112233445",    # Landline without prefix
            "70123456",      # Foreign number without + or 00 prefix
            "12345678",      # Generic short number
            "abc0933123",    # Non-digits
        ]
        for num in invalid_numbers:
            with self.assertRaises(ValidationError, msg=f"Should reject: {num}"):
                validate_phone_number(num)

    # 2. Appointment Working Hours Validation Tests (09:00 AM to 22:00 PM)
    def test_appointment_within_working_hours_succeeds(self):
        """Appointments between 09:00 and 22:00 should save successfully."""
        appt = Appointment(
            animal=self.test_patient,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=1),
            time=datetime.time(10, 0),
            duration=30,
        )
        appt.full_clean()
        appt.save()
        self.assertIsNotNone(appt.pk)

    def test_appointment_before_opening_hours_fails(self):
        """Appointments starting before 09:00 must raise ValidationError."""
        appt = Appointment(
            animal=self.test_patient,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=1),
            time=datetime.time(8, 30),
            duration=30,
        )
        with self.assertRaises(ValidationError) as ctx:
            appt.full_clean()
        self.assertIn("خارج أوقات دوام العيادة", str(ctx.exception))

    def test_appointment_ending_after_closing_hours_fails(self):
        """Appointments ending past 22:00 must raise ValidationError."""
        appt = Appointment(
            animal=self.test_patient,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=1),
            time=datetime.time(21, 45),
            duration=30,  # Ends at 22:15
        )
        with self.assertRaises(ValidationError) as ctx:
            appt.full_clean()
        self.assertIn("خارج أوقات دوام العيادة", str(ctx.exception))

    # 3. Permanent Deletion & Bulk Permanent Deletion Tests across models
    def test_client_hard_delete_and_bulk_hard_delete(self):
        """Test permanent deletion and bulk deletion for clients in trash."""
        c1 = Client.objects.create(full_name="عميل 1", phone="0933000001")
        c2 = Client.objects.create(full_name="عميل 2", phone="0933000002")
        c1.soft_delete()
        c2.soft_delete()

        # Hard delete single
        response = self.client_http.post(reverse("clients:hard_delete", args=[c1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Client.all_objects.filter(pk=c1.pk).exists())

        # Bulk hard delete
        c3 = Client.objects.create(full_name="عميل 3", phone="0933000003")
        c3.soft_delete()
        response = self.client_http.post(
            reverse("clients:bulk_hard_delete"),
            {"selected_ids": [c2.pk, c3.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Client.all_objects.filter(pk__in=[c2.pk, c3.pk]).exists())

    def test_patient_hard_delete_and_bulk_hard_delete(self):
        """Test permanent deletion and bulk deletion for patients in trash."""
        p1 = Animal.objects.create(name="مريض 1", species=Animal.Species.DOG, client=self.test_client)
        p2 = Animal.objects.create(name="مريض 2", species=Animal.Species.CAT, client=self.test_client)
        p1.soft_delete()
        p2.soft_delete()

        # Hard delete single
        response = self.client_http.post(reverse("patients:hard_delete", args=[p1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Animal.all_objects.filter(pk=p1.pk).exists())

        # Bulk hard delete
        response = self.client_http.post(
            reverse("patients:bulk_hard_delete"),
            {"selected_ids": [p2.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Animal.all_objects.filter(pk=p2.pk).exists())

    def test_appointment_hard_delete_and_bulk_hard_delete(self):
        """Test permanent deletion and bulk deletion for appointments in trash."""
        a1 = Appointment.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=2),
            time=datetime.time(11, 0),
        )
        a2 = Appointment.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=2),
            time=datetime.time(12, 0),
        )
        a1.soft_delete()
        a2.soft_delete()

        # Hard delete single
        response = self.client_http.post(reverse("appointments:hard_delete", args=[a1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Appointment.all_objects.filter(pk=a1.pk).exists())

        # Bulk hard delete
        response = self.client_http.post(
            reverse("appointments:bulk_hard_delete"),
            {"selected_ids": [a2.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Appointment.all_objects.filter(pk=a2.pk).exists())

    def test_reminder_hard_delete_and_bulk_hard_delete(self):
        """Test permanent deletion and bulk deletion for reminders in trash."""
        r1 = Reminder.objects.create(
            animal=self.test_patient,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=timezone.localdate() + datetime.timedelta(days=7),
        )
        r2 = Reminder.objects.create(
            animal=self.test_patient,
            reminder_type=Reminder.ReminderType.VACCINATION,
            due_date=timezone.localdate() + datetime.timedelta(days=14),
        )
        r1.soft_delete()
        r2.soft_delete()

        # Hard delete single
        response = self.client_http.post(reverse("reminders:hard_delete", args=[r1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Reminder.all_objects.filter(pk=r1.pk).exists())

        # Bulk hard delete
        response = self.client_http.post(
            reverse("reminders:bulk_hard_delete"),
            {"selected_ids": [r2.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Reminder.all_objects.filter(pk=r2.pk).exists())

    def test_clinical_record_hard_delete_and_bulk_hard_delete(self):
        """Test permanent deletion and bulk deletion for medical records in trash."""
        m1 = MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.CHECKUP,
            diagnosis="فحص عام روتيني",
        )
        m2 = MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.SURGERY,
            diagnosis="عملية تعقيم",
        )
        m1.soft_delete()
        m2.soft_delete()

        # Hard delete single
        response = self.client_http.post(reverse("clinical:hard_delete", args=[m1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MedicalRecord.all_objects.filter(pk=m1.pk).exists())

        # Bulk hard delete
        response = self.client_http.post(
            reverse("clinical:bulk_hard_delete"),
            {"selected_ids": [m2.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MedicalRecord.all_objects.filter(pk=m2.pk).exists())

    # 4. Appointment Status Synchronization Tests
    def test_appointment_status_update_ajax(self):
        """Test AJAX status update returns updated JSON and persists change."""
        appt = Appointment.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=3),
            time=datetime.time(14, 0),
            status=Appointment.Status.SCHEDULED,
        )

        response = self.client_http.post(
            reverse("appointments:update_status", args=[appt.pk]),
            {"status": "COMPLETED"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "COMPLETED")

        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)

    # 5. Dashboard Top Patients by Appointments & Visits Tests
    def test_dashboard_top_patients_stats(self):
        """Test that dashboard displays top patients by appointments and visits with owner names."""
        client_b = Client.objects.create(full_name="فادي خليل", phone="0944556677")
        patient_b = Animal.objects.create(name="روكي", species=Animal.Species.DOG, client=client_b)

        # Patient B has 2 appointments and 1 visit (total = 3)
        Appointment.objects.create(
            animal=patient_b,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=1),
            time=datetime.time(10, 0),
        )
        Appointment.objects.create(
            animal=patient_b,
            doctor=self.admin,
            date=timezone.localdate() + datetime.timedelta(days=2),
            time=datetime.time(11, 0),
        )
        MedicalRecord.objects.create(
            animal=patient_b,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.CHECKUP,
        )

        # Test patient (بيسو) has 1 visit (total = 1)
        MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.VISIT,
        )

        response = self.client_http.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("top_patients", response.context)
        top_list = list(response.context["top_patients"])
        self.assertTrue(len(top_list) >= 2)
        # First should be patient_b (total_activity = 3)
        self.assertEqual(top_list[0].pk, patient_b.pk)
        self.assertEqual(top_list[0].total_activity, 3)
        self.assertEqual(top_list[0].client.full_name, "فادي خليل")
        # Second should be test_patient (total_activity = 1)
        self.assertEqual(top_list[1].pk, self.test_patient.pk)
        self.assertEqual(top_list[1].total_activity, 1)
        self.assertEqual(top_list[1].client.full_name, "طارق العلي")
        # HTML content check
        self.assertContains(response, "المرضى الأكثر تسجيلاً للمواعيد والزيارات السريرية")
        self.assertContains(response, "روكي")
        self.assertContains(response, "فادي خليل")

    def test_procedures_classification_in_dashboard(self):
        """Test that clinical procedures are accurately categorized and counted in the dashboard."""
        today = timezone.now()
        # 1. Routine Visit
        MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.VISIT,
            date_time=today,
        )
        # 2. Checkup
        MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.CHECKUP,
            date_time=today,
        )
        # 3. Surgery
        MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.SURGERY,
            date_time=today,
        )
        # 4. Emergency
        MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.EMERGENCY,
            date_time=today,
        )
        # 5. Vaccination record
        MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.VACCINATION,
            vaccine_name="Rabies Vaccine",
            next_vaccination_date=timezone.localdate() + datetime.timedelta(days=365),
            date_time=today,
        )
        # 6. Visit with vaccine administered
        MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin,
            record_type=MedicalRecord.RecordType.VISIT,
            vaccine_name="DHPP",
            next_vaccination_date=timezone.localdate() + datetime.timedelta(days=180),
            date_time=today,
        )

        response = self.client_http.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

        # Check procedure counts
        self.assertEqual(response.context["checkup_count"], 2)
        self.assertEqual(response.context["surgery_count"], 1)
        self.assertEqual(response.context["emergency_count"], 1)
        self.assertEqual(response.context["vaccination_records_count"], 2)
        self.assertEqual(response.context["clinical_visits_count"], 6)

        # Verify JSON data for Chart.js
        import json
        labels = json.loads(response.context["procedures_labels_json"])
        data = json.loads(response.context["procedures_data_json"])
        self.assertIn("فحوصات وزيارات", labels)
        self.assertIn("عمليات جراحية", labels)
        self.assertIn("طوارئ وإسعاف", labels)
        self.assertIn("تطعيمات ولقاحات", labels)
        self.assertEqual(data, [2, 1, 1, 2])

    def test_top_patients_partial_endpoint_and_filtering(self):
        """Test HTMX partial endpoint for top patients with periods and metrics."""
        patient_c = Animal.objects.create(
            name="سيمبا",
            species=Animal.Species.CAT,
            client=self.test_client,
            gender=Animal.Gender.MALE,
        )
        # Create 3 visits for simba and 1 appointment
        for _ in range(3):
            MedicalRecord.objects.create(
                animal=patient_c,
                doctor=self.admin,
                record_type=MedicalRecord.RecordType.VISIT,
            )
        Appointment.objects.create(
            animal=patient_c,
            doctor=self.admin,
            date=timezone.localdate(),
            time=datetime.time(12, 0),
        )

        # Create 5 appointments for test_patient
        for i in range(5):
            Appointment.objects.create(
                animal=self.test_patient,
                doctor=self.admin,
                date=timezone.localdate(),
                time=datetime.time(14 + i, 0),
            )

        url = reverse("core:top_patients_partial")

        # 1. Test metric=appointments
        res_appts = self.client_http.get(f"{url}?top_period=this_month&top_metric=appointments&top_limit=5")
        self.assertEqual(res_appts.status_code, 200)
        self.assertIn("top-patients-container", res_appts.content.decode("utf-8"))
        top_appts = res_appts.context["top_patients"]
        self.assertEqual(top_appts[0].pk, self.test_patient.pk)
        self.assertEqual(top_appts[0].appointments_count, 5)

        # 2. Test metric=visits
        res_visits = self.client_http.get(f"{url}?top_period=this_month&top_metric=visits&top_limit=5")
        self.assertEqual(res_visits.status_code, 200)
        top_vis = res_visits.context["top_patients"]
        self.assertEqual(top_vis[0].pk, patient_c.pk)
        self.assertEqual(top_vis[0].visits_count, 3)

        # 3. Test metric=total
        res_total = self.client_http.get(f"{url}?top_period=this_month&top_metric=total&top_limit=5")
        self.assertEqual(res_total.status_code, 200)
        top_tot = res_total.context["top_patients"]
        # test_patient has 5 appointments + 0 visits = 5
        # patient_c has 1 appointment + 3 visits = 4
        self.assertEqual(top_tot[0].pk, self.test_patient.pk)
        self.assertEqual(top_tot[0].total_activity, 5)
        self.assertEqual(top_tot[1].pk, patient_c.pk)
        self.assertEqual(top_tot[1].total_activity, 4)
