import datetime
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.clients.models import Client
from apps.patients.models import Animal
from apps.appointments.models import Appointment
from apps.reminders.models import Reminder
from apps.clinical.models import MedicalRecord, FileAttachment, VaccinationRecord, validate_attachment_size
from apps.audit.models import AuditLog


class ClinicalBusinessRulesAndViewsTests(TestCase):
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
            full_name="طارق يوسف",
            phone="0988776655",
            address="دمشق - الشعلان",
        )
        self.patient = Animal.objects.create(
            name="سيمبا",
            species=Animal.Species.CAT,
            client=self.owner,
            weight=3.8,
        )

    def test_medical_record_walk_in_creation_and_weight_update(self):
        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "weight_at_visit": "4.2",
            "symptoms": "خمول وارتفاع خفيف بالحرارة",
            "diagnosis": "نزلة برد خفيفة",
            "treatment": "إعطاء خافض حرارة ومضاد حيوي",
            "prescription": "أموكسيسيلين قطرات مرتين يومياً",
            "notes": "المراجعة بعد 3 أيام في حال استمرار الأعراض",
        }
        response = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        rec = MedicalRecord.objects.filter(animal=self.patient).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.diagnosis, "نزلة برد خفيفة")
        self.assertEqual(rec.doctor, self.vet_dr_ali)

        # Verify patient's latest weight was automatically updated
        self.patient.refresh_from_db()
        self.assertEqual(float(self.patient.weight), 4.2)

        # Verify Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                entity_id=str(rec.pk),
            ).exists()
        )

    def test_medical_record_from_appointment_completes_appointment(self):
        appt = Appointment.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            date=timezone.localdate(),
            time=datetime.time(10, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "appointment": str(appt.pk),
            "record_type": MedicalRecord.RecordType.CHECKUP,
            "date_time": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "فحص سليم",
        }
        response = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        # Verify appointment marked as COMPLETED
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)

    def test_attachment_size_validation_enforced_15mb(self):
        """Backend file validation strictly limits attachments to 15MB."""
        # 1. Valid file (1 KB)
        small_file = SimpleUploadedFile("xray.jpg", b"dummy image data" * 64, content_type="image/jpeg")
        validate_attachment_size(small_file)  # Should not raise

        # 2. Oversized file (> 15 MB)
        oversized_file = SimpleUploadedFile("big_scan.pdf", b"X" * (16 * 1024 * 1024), content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_attachment_size(oversized_file)

    def test_attachment_upload_and_delete(self):
        sample_file = SimpleUploadedFile("lab_result.pdf", b"%PDF-1.4 sample lab report", content_type="application/pdf")
        post_data = {
            "animal": str(self.patient.pk),
            "file": sample_file,
        }
        response = self.client_runner.post(reverse("clinical:attachment_upload"), data=post_data)
        self.assertEqual(response.status_code, 302)

        att = FileAttachment.objects.filter(animal=self.patient).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.file_name, "lab_result.pdf")
        self.assertTrue(att.file_size > 0)

        # Delete attachment
        del_res = self.client_runner.post(reverse("clinical:attachment_delete", args=[att.pk]))
        self.assertEqual(del_res.status_code, 302)
        att.refresh_from_db()
        self.assertTrue(att.is_deleted)

    def test_vaccination_record_and_auto_reminder_generation(self):
        """Registering a vaccination with next_due_date automatically generates a Reminder."""
        next_due = timezone.localdate() + datetime.timedelta(days=365)
        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "vaccine_name": "اللقاح الرباعي للقطط (FVRCP)",
            "date_administered": timezone.localdate().strftime("%Y-%m-%d"),
            "next_due_date": next_due.strftime("%Y-%m-%d"),
            "batch_number": "LOT-2026-99",
            "notes": "الجرعة الأولى مع استجابة طبيعية",
        }
        response = self.client_runner.post(reverse("clinical:vaccination_create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        vac = VaccinationRecord.objects.filter(animal=self.patient).first()
        self.assertIsNotNone(vac)
        self.assertEqual(vac.vaccine_name, "اللقاح الرباعي للقطط (FVRCP)")
        self.assertIsNotNone(vac.reminder)

        # Verify automatically generated Reminder
        rem = vac.reminder
        self.assertEqual(rem.animal, self.patient)
        self.assertEqual(rem.reminder_type, Reminder.ReminderType.VACCINATION)
        self.assertEqual(rem.due_date, next_due)
        self.assertEqual(rem.status, Reminder.Status.PENDING)

    def test_soft_delete_and_restore_clinical_records(self):
        rec = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            diagnosis="فحص أولي",
        )

        # Delete
        del_res = self.client_runner.post(reverse("clinical:delete", args=[rec.pk]))
        self.assertEqual(del_res.status_code, 302)
        rec.refresh_from_db()
        self.assertTrue(rec.is_deleted)
        self.assertFalse(MedicalRecord.objects.alive().filter(pk=rec.pk).exists())

        # Restore
        restore_res = self.client_runner.post(reverse("clinical:restore", args=[rec.pk]))
        self.assertEqual(restore_res.status_code, 302)
        rec.refresh_from_db()
        self.assertFalse(rec.is_deleted)

    def test_filter_deleted_clinical_records(self):
        """Verify that trash filter (both filter_deleted=deleted and status=deleted) correctly activates and filters records."""
        active_rec = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            diagnosis="سجل نشط",
        )
        deleted_rec = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            diagnosis="سجل محذوف",
        )
        deleted_rec.soft_delete()

        # 1. Default view (active only)
        res_default = self.client_runner.get(reverse("clinical:list"))
        self.assertEqual(res_default.status_code, 200)
        self.assertIn(active_rec, res_default.context["records"])
        self.assertNotIn(deleted_rec, res_default.context["records"])
        self.assertEqual(res_default.context["filter_deleted"], "active")

        # 2. Filter using filter_deleted=deleted
        res_trash = self.client_runner.get(reverse("clinical:list") + "?filter_deleted=deleted")
        self.assertEqual(res_trash.status_code, 200)
        self.assertIn(deleted_rec, res_trash.context["records"])
        self.assertNotIn(active_rec, res_trash.context["records"])
        self.assertEqual(res_trash.context["filter_deleted"], "deleted")

        # 3. Filter using status=deleted (fallback / compatibility)
        res_status = self.client_runner.get(reverse("clinical:list") + "?status=deleted")
        self.assertEqual(res_status.status_code, 200)
        self.assertIn(deleted_rec, res_status.context["records"])
        self.assertNotIn(active_rec, res_status.context["records"])
        self.assertEqual(res_status.context["filter_deleted"], "deleted")


    def test_medical_record_with_multiple_services(self):
        """Test creating and updating clinical visit with multiple services."""
        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "فحص وعلاج شامل",
            "service_name": ["علاج وجروح", "قص أظافر", "حمام وتجفيف"],
            "service_notes": ["تنظيف وتضميد", "أطراف أمامية وخلفية", "شامبو طبي"],
        }
        response = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        rec = MedicalRecord.objects.filter(animal=self.patient).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.services.count(), 3)
        self.assertTrue(rec.services.filter(name="علاج وجروح").exists())
        self.assertTrue(rec.services.filter(name="قص أظافر").exists())
        self.assertTrue(rec.services.filter(name="حمام وتجفيف").exists())

        # Test updating services
        update_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "تعديل الزيارة",
            "service_name": ["حقنة مضاد حيوي"],
            "service_notes": ["عضلي"],
        }
        up_res = self.client_runner.post(reverse("clinical:update", args=[rec.pk]), data=update_data)
        self.assertEqual(up_res.status_code, 302)
        self.assertEqual(rec.services.count(), 1)
        self.assertEqual(rec.services.first().name, "حقنة مضاد حيوي")

    def test_vaccination_visit_mandatory_next_date_validation(self):
        """Vaccination record type strictly requires next_vaccination_date."""
        # 1. Omitting next_vaccination_date on VACCINATION visit raises validation error
        post_data_invalid = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VACCINATION,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "vaccine_name": "داء الكلب Rabies",
            "next_vaccination_date": "",
        }
        res_invalid = self.client_runner.post(reverse("clinical:create"), data=post_data_invalid)
        self.assertEqual(res_invalid.status_code, 302)
        self.assertFalse(MedicalRecord.objects.filter(record_type=MedicalRecord.RecordType.VACCINATION).exists())

        # 2. Providing next_vaccination_date succeeds and creates linked reminder
        next_due = timezone.localdate() + datetime.timedelta(days=180)
        post_data_valid = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VACCINATION,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "vaccine_name": "داء الكلب Rabies",
            "next_vaccination_date": next_due.strftime("%Y-%m-%d"),
            "batch_number": "LOT-RB-77",
        }
        res_valid = self.client_runner.post(reverse("clinical:create"), data=post_data_valid)
        self.assertEqual(res_valid.status_code, 302)
        vac_rec = MedicalRecord.objects.filter(record_type=MedicalRecord.RecordType.VACCINATION).first()
        self.assertIsNotNone(vac_rec)
        self.assertEqual(vac_rec.next_vaccination_date, next_due)
        # Check auto reminder created
        self.assertTrue(Reminder.objects.filter(animal=self.patient, reminder_type=Reminder.ReminderType.VACCINATION, due_date=next_due).exists())

    def test_cascading_vaccination_and_reminder_update(self):
        """Updating a vaccination visit seamlessly updates the linked Reminder without duplicates."""
        initial_due = timezone.localdate() + datetime.timedelta(days=30)
        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VACCINATION,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "vaccine_name": "لقاح السعار (خطأ مطبعي)",
            "next_vaccination_date": initial_due.strftime("%Y-%m-%d"),
            "batch_number": "LOT-OLD-01",
        }
        res = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(res.status_code, 302)

        vac_rec = MedicalRecord.objects.filter(record_type=MedicalRecord.RecordType.VACCINATION).first()
        self.assertIsNotNone(vac_rec)
        rem = Reminder.objects.filter(animal=self.patient, reminder_type=Reminder.ReminderType.VACCINATION).first()
        self.assertIsNotNone(rem)
        self.assertIn("خطأ مطبعي", rem.notes)
        self.assertEqual(rem.due_date, initial_due)
        original_rem_id = rem.pk

        # Update visit to fix typo and change due date
        updated_due = timezone.localdate() + datetime.timedelta(days=60)
        update_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VACCINATION,
            "date_time": vac_rec.date_time.strftime("%Y-%m-%dT%H:%M"),
            "vaccine_name": "لقاح السعار Rabies Vaccine المصحح",
            "next_vaccination_date": updated_due.strftime("%Y-%m-%d"),
            "batch_number": "LOT-NEW-02",
        }
        res_update = self.client_runner.post(reverse("clinical:update", args=[vac_rec.pk]), data=update_data)
        self.assertEqual(res_update.status_code, 302)

        # Check that Reminder was updated in place with NO duplicate created
        all_rems = Reminder.objects.alive().filter(animal=self.patient, reminder_type=Reminder.ReminderType.VACCINATION)
        self.assertEqual(all_rems.count(), 1)
        updated_rem = all_rems.first()
        self.assertEqual(updated_rem.pk, original_rem_id)
        self.assertEqual(updated_rem.due_date, updated_due)
        self.assertIn("المصحح", updated_rem.notes)

        # Change visit type to regular VISIT (removing vaccination) and ensure pending reminder is cleaned up
        clear_data = update_data.copy()
        clear_data["record_type"] = MedicalRecord.RecordType.VISIT
        clear_data["vaccine_name"] = ""
        clear_data["next_vaccination_date"] = ""
        res_clear = self.client_runner.post(reverse("clinical:update", args=[vac_rec.pk]), data=clear_data)
        self.assertEqual(res_clear.status_code, 302)
        self.assertFalse(Reminder.objects.alive().filter(animal=self.patient, reminder_type=Reminder.ReminderType.VACCINATION).exists())

    def test_attachment_delete_ownership_permission(self):
        """Non-admin user cannot delete another user's attachment, but can delete their own; Admin can delete any."""
        vet_dr_sara = User.objects.create_user(
            username="dr_sara",
            password="password123",
            first_name="سارة",
            role=User.Role.VET,
        )

        from django.contrib.auth.models import Permission
        del_perm = Permission.objects.get(codename="can_delete")
        vet_dr_sara.user_permissions.add(del_perm)
        self.vet_dr_ali.user_permissions.add(del_perm)

        file1 = SimpleUploadedFile("doc1.pdf", b"pdf content 1", content_type="application/pdf")
        att1 = FileAttachment.objects.create(
            animal=self.patient,
            file=file1,
            file_name="doc1.pdf",
            file_size=13,
            uploaded_by=self.vet_dr_ali,
        )

        # 1. Login as Dr. Sara (different doctor / non-admin) -> Cannot delete Dr. Ali's attachment
        self.client_runner.login(username="dr_sara", password="password123")
        res_unauth = self.client_runner.post(reverse("clinical:attachment_delete", args=[att1.pk]))
        self.assertEqual(res_unauth.status_code, 302)
        att1.refresh_from_db()
        self.assertFalse(att1.is_deleted)

        # 2. Login as Dr. Ali (the uploader) -> Can delete own attachment
        self.client_runner.login(username="dr_ali", password="password123")
        res_auth = self.client_runner.post(reverse("clinical:attachment_delete", args=[att1.pk]))
        self.assertEqual(res_auth.status_code, 302)
        att1.refresh_from_db()
        self.assertTrue(att1.is_deleted)

        # 3. Create another attachment uploaded by Dr. Ali, Admin can delete it
        file2 = SimpleUploadedFile("doc2.pdf", b"pdf content 2", content_type="application/pdf")
        att2 = FileAttachment.objects.create(
            animal=self.patient,
            file=file2,
            file_name="doc2.pdf",
            file_size=13,
            uploaded_by=self.vet_dr_ali,
        )
        self.client_runner.login(username="admin_user", password="password123")
        res_admin = self.client_runner.post(reverse("clinical:attachment_delete", args=[att2.pk]))
        self.assertEqual(res_admin.status_code, 302)
        att2.refresh_from_db()
        self.assertTrue(att2.is_deleted)

    def test_medical_record_rejects_appointment_with_different_animal(self):
        """MedicalRecord model and form reject linking an appointment of another animal."""
        other_patient = Animal.objects.create(
            name="روكي",
            species=Animal.Species.DOG,
            client=self.owner,
        )
        other_appt = Appointment.objects.create(
            animal=other_patient,
            doctor=self.vet_dr_ali,
            date=timezone.localdate(),
            time=datetime.time(11, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        # 1. Direct Model validation
        rec = MedicalRecord(
            animal=self.patient,  # Simba
            doctor=self.vet_dr_ali,
            appointment=other_appt,  # Rocky's appointment
            diagnosis="محاولة ربط خاطئ",
        )
        with self.assertRaises(ValidationError) as ctx:
            rec.full_clean()
        self.assertIn("appointment", ctx.exception.message_dict)

        # 2. View / Form submission validation
        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "appointment": str(other_appt.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "محاولة ربط خاطئ من الواجهة",
        }
        res = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(res.status_code, 302)
        # Verify no record created and appointment remains SCHEDULED
        self.assertFalse(MedicalRecord.objects.filter(diagnosis="محاولة ربط خاطئ من الواجهة").exists())
        other_appt.refresh_from_db()
        self.assertEqual(other_appt.status, Appointment.Status.SCHEDULED)

    def test_medical_record_rejects_appointment_with_different_doctor(self):
        """MedicalRecord model and form reject linking an appointment of another doctor."""
        vet_dr_sara = User.objects.create_user(
            username="dr_sara_test",
            password="password123",
            first_name="سارة",
            role=User.Role.VET,
        )
        dr_sara_appt = Appointment.objects.create(
            animal=self.patient,
            doctor=vet_dr_sara,
            date=timezone.localdate(),
            time=datetime.time(12, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        # 1. Direct Model validation
        rec = MedicalRecord(
            animal=self.patient,
            doctor=self.vet_dr_ali,  # Dr. Ali
            appointment=dr_sara_appt,  # Dr. Sara's appointment
            diagnosis="محاولة ربط طبيب مختلف",
        )
        with self.assertRaises(ValidationError) as ctx:
            rec.full_clean()
        self.assertIn("appointment", ctx.exception.message_dict)

        # 2. View / Form submission validation
        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "appointment": str(dr_sara_appt.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "محاولة ربط طبيب مختلف من الواجهة",
        }
        res = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(MedicalRecord.objects.filter(diagnosis="محاولة ربط طبيب مختلف من الواجهة").exists())
        dr_sara_appt.refresh_from_db()
        self.assertEqual(dr_sara_appt.status, Appointment.Status.SCHEDULED)

    def test_medical_record_rejects_cancelled_or_deleted_appointment(self):
        """MedicalRecord rejects linking a CANCELLED or soft-deleted appointment."""
        cancelled_appt = Appointment.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            date=timezone.localdate(),
            time=datetime.time(14, 0),
            duration=30,
            status=Appointment.Status.CANCELLED,
        )

        rec = MedicalRecord(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            appointment=cancelled_appt,
            diagnosis="محاولة ربط موعد ملغى",
        )
        with self.assertRaises(ValidationError) as ctx:
            rec.full_clean()
        self.assertIn("appointment", ctx.exception.message_dict)

    def test_medical_record_rejects_future_appointment_linking(self):
        """MedicalRecord cannot be linked to a future appointment scheduled for upcoming days."""
        future_date = timezone.localdate() + datetime.timedelta(days=5)
        future_appt = Appointment.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            date=future_date,
            time=datetime.time(10, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        # 1. Direct Model validation
        rec = MedicalRecord(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            appointment=future_appt,
            date_time=timezone.now(),
            diagnosis="فحص مبكر لموعد قادم",
        )
        with self.assertRaises(ValidationError) as ctx:
            rec.full_clean()
        self.assertIn("appointment", ctx.exception.message_dict)

        # 2. View validation: Linking future appointment fails
        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "appointment": str(future_appt.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "محاولة ربط موعد مستقبلي",
        }
        res = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(MedicalRecord.objects.filter(diagnosis="محاولة ربط موعد مستقبلي").exists())
        future_appt.refresh_from_db()
        self.assertEqual(future_appt.status, Appointment.Status.SCHEDULED)

        # 3. Patient arriving early as Walk-in (without linking future appointment) succeeds
        walk_in_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "زيارة مباشرة (Walk-in)",
        }
        res_walk_in = self.client_runner.post(reverse("clinical:create"), data=walk_in_data)
        self.assertEqual(res_walk_in.status_code, 302)
        self.assertTrue(MedicalRecord.objects.filter(diagnosis="زيارة مباشرة (Walk-in)").exists())
        # Future appointment remains active and SCHEDULED
        future_appt.refresh_from_db()
        self.assertEqual(future_appt.status, Appointment.Status.SCHEDULED)

    def test_clinical_records_filtering_by_type_and_vaccine(self):
        """Test clinical records list view filtering by record_type and vaccine_name."""
        rec_checkup = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            record_type=MedicalRecord.RecordType.CHECKUP,
            diagnosis="فحص دوري",
        )
        rec_vac1 = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            record_type=MedicalRecord.RecordType.VACCINATION,
            vaccine_name="تطعيم الثلاثي",
            next_vaccination_date=timezone.localdate() + datetime.timedelta(days=365),
        )
        rec_vac2 = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            record_type=MedicalRecord.RecordType.VACCINATION,
            vaccine_name="لقاح السعار",
            next_vaccination_date=timezone.localdate() + datetime.timedelta(days=365),
        )

        # 1. Filter by record_type = VACCINATION
        res = self.client_runner.get(reverse("clinical:list"), {"record_type": "VACCINATION"})
        self.assertEqual(res.status_code, 200)
        records = list(res.context["records"])
        self.assertIn(rec_vac1, records)
        self.assertIn(rec_vac2, records)
        self.assertNotIn(rec_checkup, records)

        # 2. Filter by record_type = VACCINATION and vaccine_name = تطعيم الثلاثي
        res2 = self.client_runner.get(reverse("clinical:list"), {
            "record_type": "VACCINATION",
            "vaccine_name": "تطعيم الثلاثي",
        })
        self.assertEqual(res2.status_code, 200)
    def test_clinical_record_update_parity(self):
        """Test that updating a medical record supports appointment completion, reminder, notes, and attachment."""
        rec = MedicalRecord.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            record_type=MedicalRecord.RecordType.VISIT,
            date_time=timezone.now(),
            diagnosis="تشخيص مبدئي",
        )

        appt = Appointment.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            date=timezone.localdate(),
            time=datetime.time(11, 0),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )

        dummy_file = SimpleUploadedFile("xray_update.pdf", b"%PDF-dummy-content", content_type="application/pdf")
        update_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "appointment": str(appt.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "weight_at_visit": "4.5",
            "diagnosis": "تشخيص محدث بعد الفحص",
            "notes": "ملاحظات إضافية تم تعديلها",
            "create_reminder": "true",
            "reminder_type": "FOLLOW_UP",
            "reminder_due_date": (timezone.localdate() + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
            "reminder_notes": "تذكير متابعة بعد التعديل",
            "attachment_file": dummy_file,
        }

        res = self.client_runner.post(reverse("clinical:update", args=[rec.pk]), data=update_data)
        self.assertEqual(res.status_code, 302)

        rec.refresh_from_db()
        self.assertEqual(rec.diagnosis, "تشخيص محدث بعد الفحص")
        self.assertEqual(rec.notes, "ملاحظات إضافية تم تعديلها")
        self.assertEqual(rec.appointment, appt)

        # 1. Verify linked appointment was marked COMPLETED
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)

        # 2. Verify patient weight was updated
        self.patient.refresh_from_db()
        self.assertEqual(float(self.patient.weight), 4.5)

        # 3. Verify reminder was created
        rem = Reminder.objects.filter(animal=self.patient, medical_record=rec).first()
        self.assertIsNotNone(rem)
        self.assertEqual(rem.reminder_type, Reminder.ReminderType.FOLLOW_UP)
        self.assertEqual(rem.notes, "تذكير متابعة بعد التعديل")

        # 4. Verify file attachment was created
        att = FileAttachment.objects.filter(medical_record=rec).first()
        self.assertIsNotNone(att)
        self.assertTrue(att.file_name.startswith("xray_update"))

    def test_patient_detail_appointments_context(self):
        """Test that patient_detail view passes patient_appointments to template."""
        appt1 = Appointment.objects.create(
            animal=self.patient,
            doctor=self.vet_dr_ali,
            date=timezone.localdate(),
            time=datetime.time(9, 30),
            duration=30,
            status=Appointment.Status.SCHEDULED,
        )
        res = self.client_runner.get(reverse("patients:detail", args=[self.patient.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertIn("patient_appointments", res.context)
        self.assertIn(appt1, res.context["patient_appointments"])

    def test_multiple_vaccinations_creation_with_different_next_vaccine(self):
        """Test recording multiple vaccines in a single visit with distinct next vaccine names and reminders."""
        next_due_1 = timezone.localdate() + datetime.timedelta(days=30)
        next_due_2 = timezone.localdate() + datetime.timedelta(days=365)

        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VACCINATION,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "weight_at_visit": "4.0",
            "diagnosis": "تطعيم دوري متعدد",
            "vac_name[]": ["اللقاح الرباعي للقطط (FVRCP)", "لقاح داء الكلب (Rabies)"],
            "vac_batch[]": ["LOT-A101", "LOT-B202"],
            "vac_next_name[]": ["الجرعة التنشيطية للرباعي", "لقاح داء الكلب السنوي"],
            "vac_next_date[]": [next_due_1.isoformat(), next_due_2.isoformat()],
            "vac_notes[]": ["إعطاء تحت الجلد بالكتف الأيسر", "إعطاء بالفخذ الأيمن"],
        }

        res = self.client_runner.post(reverse("clinical:create"), data=post_data)
        self.assertEqual(res.status_code, 302)

        rec = MedicalRecord.objects.filter(animal=self.patient, record_type=MedicalRecord.RecordType.VACCINATION).first()
        self.assertIsNotNone(rec)

        # Verify multiple VaccinationRecords created
        vacs = list(rec.vaccination_records.alive().order_by("date_administered", "id"))
        self.assertEqual(len(vacs), 2)

        # Check first vaccine
        v1 = vacs[0]
        self.assertEqual(v1.vaccine_name, "اللقاح الرباعي للقطط (FVRCP)")
        self.assertEqual(v1.batch_number, "LOT-A101")
        self.assertEqual(v1.next_vaccine_name, "الجرعة التنشيطية للرباعي")
        self.assertEqual(v1.next_due_date, next_due_1)
        self.assertIsNotNone(v1.reminder)
        self.assertEqual(v1.reminder.due_date, next_due_1)
        self.assertIn("الجرعة التنشيطية للرباعي", v1.reminder.notes)

        # Check second vaccine
        v2 = vacs[1]
        self.assertEqual(v2.vaccine_name, "لقاح داء الكلب (Rabies)")
        self.assertEqual(v2.batch_number, "LOT-B202")
        self.assertEqual(v2.next_vaccine_name, "لقاح داء الكلب السنوي")
        self.assertEqual(v2.next_due_date, next_due_2)
        self.assertIsNotNone(v2.reminder)
        self.assertEqual(v2.reminder.due_date, next_due_2)
        self.assertIn("لقاح داء الكلب السنوي", v2.reminder.notes)

        # Verify backward compatibility fields on MedicalRecord match first vaccine
        self.assertEqual(rec.vaccine_name, "اللقاح الرباعي للقطط (FVRCP)")
        self.assertEqual(rec.batch_number, "LOT-A101")
        self.assertEqual(rec.next_vaccine_name, "الجرعة التنشيطية للرباعي")
        self.assertEqual(rec.next_vaccination_date, next_due_1)

    def test_multiple_vaccinations_update_and_removal(self):
        """Test updating a visit's vaccines and removing one of the administered vaccines."""
        next_due_1 = timezone.localdate() + datetime.timedelta(days=30)
        next_due_2 = timezone.localdate() + datetime.timedelta(days=180)

        post_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "فحص وتطعيم",
            "vac_name[]": ["لقاح أ", "لقاح ب"],
            "vac_batch[]": ["B1", "B2"],
            "vac_next_name[]": ["لقاح أ", "لقاح ج"],
            "vac_next_date[]": [next_due_1.isoformat(), next_due_2.isoformat()],
            "vac_notes[]": ["", ""],
        }
        self.client_runner.post(reverse("clinical:create"), data=post_data)

        rec = MedicalRecord.objects.filter(animal=self.patient).first()
        self.assertEqual(rec.vaccination_records.alive().count(), 2)
        self.assertEqual(Reminder.objects.filter(animal=self.patient, status=Reminder.Status.PENDING).count(), 2)

        # Now update by keeping only 1 vaccine
        update_data = {
            "animal": str(self.patient.pk),
            "doctor": str(self.vet_dr_ali.pk),
            "record_type": MedicalRecord.RecordType.VISIT,
            "date_time": rec.date_time.strftime("%Y-%m-%dT%H:%M"),
            "diagnosis": "فحص وتطعيم محدث",
            "vac_name[]": ["لقاح أ"],
            "vac_batch[]": ["B1-UPDATED"],
            "vac_next_name[]": ["لقاح أ"],
            "vac_next_date[]": [next_due_1.isoformat()],
            "vac_notes[]": ["تم إعطاء الجرعة"],
        }
        res_update = self.client_runner.post(reverse("clinical:update", args=[rec.pk]), data=update_data)
        self.assertEqual(res_update.status_code, 302)

        # Verify only 1 active vaccine remains, the second was cleanly soft-deleted
        self.assertEqual(rec.vaccination_records.alive().count(), 1)
        self.assertEqual(rec.vaccination_records.all_with_deleted().count(), 2) # total including soft deleted
        self.assertEqual(rec.vaccination_records.deleted_only().count(), 1)
        self.assertEqual(Reminder.objects.filter(animal=self.patient, status=Reminder.Status.PENDING).count(), 1)






