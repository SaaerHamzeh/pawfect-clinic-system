from django.test import TestCase, Client as TestClient
from django.urls import reverse
from apps.accounts.models import User
from apps.clients.models import Client
from apps.audit.models import AuditLog


class ClientViewsAndBusinessRulesTests(TestCase):
    def setUp(self):
        self.client_runner = TestClient()
        self.admin_user = User.objects.create_superuser(
            username="admin_user",
            password="password123",
            role=User.Role.ADMIN,
        )
        self.staff_user = User.objects.create_user(
            username="staff_user",
            password="password123",
            role=User.Role.STAFF,
        )

        self.client_runner.login(username="admin_user", password="password123")

        self.sample_client = Client.objects.create(
            full_name="سعيد الأحمد",
            phone="0935111222",
            address="دمشق - المزة",
            notes="عميل تجريبي",
        )

    def test_clients_list_view_and_search(self):
        response = self.client_runner.get(reverse("clients:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سعيد الأحمد")

        # Test search query
        search_res = self.client_runner.get(reverse("clients:list"), {"q": "0935111222"})
        self.assertEqual(search_res.status_code, 200)
        self.assertContains(search_res, "سعيد الأحمد")

        search_empty = self.client_runner.get(reverse("clients:list"), {"q": "غير موجود"})
        self.assertEqual(search_empty.status_code, 200)
        self.assertNotContains(search_empty, "سعيد الأحمد")

    def test_client_detail_view(self):
        response = self.client_runner.get(reverse("clients:detail", args=[self.sample_client.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سعيد الأحمد")
        self.assertContains(response, "0935111222")

    def test_client_create_and_audit_log(self):
        post_data = {
            "full_name": "طارق علي",
            "phone": "0988776655",
            "address": "اللاذقية - المشروع",
            "notes": "عميل جديد",
        }
        response = self.client_runner.post(reverse("clients:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        created_client = Client.objects.filter(phone="0988776655").first()
        self.assertIsNotNone(created_client)
        self.assertEqual(created_client.full_name, "طارق علي")

        # Verify Audit Log
        audit_entry = AuditLog.objects.filter(
            action=AuditLog.Action.CREATE,
            entity_id=str(created_client.pk),
        ).first()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.user, self.admin_user)

    def test_client_update_and_audit_log(self):
        post_data = {
            "full_name": "سعيد الأحمد المعدل",
            "phone": "0935111222",
            "address": "دمشق - أوتوستراد المزة",
            "notes": "ملاحظات محدثة",
        }
        response = self.client_runner.post(
            reverse("clients:update", args=[self.sample_client.pk]), data=post_data
        )
        self.assertEqual(response.status_code, 302)

        self.sample_client.refresh_from_db()
        self.assertEqual(self.sample_client.full_name, "سعيد الأحمد المعدل")

        # Verify Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                entity_id=str(self.sample_client.pk),
            ).exists()
        )

    def test_client_soft_delete_and_restore(self):
        # Delete client
        del_response = self.client_runner.post(
            reverse("clients:delete", args=[self.sample_client.pk])
        )
        self.assertEqual(del_response.status_code, 302)

        self.sample_client.refresh_from_db()
        self.assertTrue(self.sample_client.is_deleted)
        self.assertIsNotNone(self.sample_client.deleted_at)

        # It shouldn't appear in default alive queryset
        self.assertFalse(Client.objects.alive().filter(pk=self.sample_client.pk).exists())
        self.assertTrue(Client.objects.deleted_only().filter(pk=self.sample_client.pk).exists())

        # Verify Delete Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE,
                entity_id=str(self.sample_client.pk),
            ).exists()
        )

        # Restore client as Admin
        restore_response = self.client_runner.post(
            reverse("clients:restore", args=[self.sample_client.pk])
        )
        self.assertEqual(restore_response.status_code, 302)

        self.sample_client.refresh_from_db()
        self.assertFalse(self.sample_client.is_deleted)
        self.assertIsNone(self.sample_client.deleted_at)

        # Verify Restore Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.RESTORE,
                entity_id=str(self.sample_client.pk),
            ).exists()
        )

    def test_client_soft_delete_and_restore_cascades_to_animals(self):
        """Soft-deleting a Client must also soft-delete its associated Animals, and restoring must restore them."""
        from apps.patients.models import Animal
        animal1 = Animal.objects.create(name="ميشو", client=self.sample_client)
        animal2 = Animal.objects.create(name="بسبوس", client=self.sample_client)

        self.assertFalse(animal1.is_deleted)
        self.assertFalse(animal2.is_deleted)

        # Soft-delete client
        self.sample_client.soft_delete()
        animal1.refresh_from_db()
        animal2.refresh_from_db()

        self.assertTrue(self.sample_client.is_deleted)
        self.assertTrue(animal1.is_deleted)
        self.assertTrue(animal2.is_deleted)

        # Restore client
        self.sample_client.restore()
        animal1.refresh_from_db()
        animal2.refresh_from_db()

        self.assertFalse(self.sample_client.is_deleted)
        self.assertFalse(animal1.is_deleted)
        self.assertFalse(animal2.is_deleted)

    def test_client_hard_delete_physically_deletes_media_files(self):
        """Hard deleting a client and cascading to animals must remove photos and attachments from disk."""
        import os
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.patients.models import Animal
        from apps.clinical.models import FileAttachment

        photo = SimpleUploadedFile("pet_photo.png", b"test photo content", content_type="image/png")
        animal = Animal.objects.create(name="روكي", client=self.sample_client, photo=photo)
        photo_path = animal.photo.path
        self.assertTrue(os.path.exists(photo_path))

        att = SimpleUploadedFile("xray.pdf", b"test pdf content", content_type="application/pdf")
        attachment = FileAttachment.objects.create(animal=animal, file=att, file_name="xray.pdf", file_size=16)
        att_path = attachment.file.path
        self.assertTrue(os.path.exists(att_path))

        # Soft delete first to put in trash
        self.sample_client.soft_delete()

        # Hard delete client
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_runner.post(reverse("clients:hard_delete", args=[self.sample_client.pk]))
        self.assertEqual(response.status_code, 302)

        # Verify files were physically removed from disk
        self.assertFalse(os.path.exists(photo_path))
        self.assertFalse(os.path.exists(att_path))

    def test_client_restore_selectivity_preserves_independently_deleted_animals(self):
        """An animal soft-deleted independently BEFORE its client was soft-deleted must NOT be restored when the client is restored."""
        import datetime
        from django.utils import timezone
        from apps.patients.models import Animal

        animal_indep = Animal.objects.create(name="حيوان محذوف فردياً", client=self.sample_client)
        animal_cascade = Animal.objects.create(name="حيوان تابع للعميل", client=self.sample_client)

        # 1. Soft-delete animal_indep independently 10 minutes prior
        animal_indep.soft_delete()
        earlier_time = timezone.now() - datetime.timedelta(minutes=10)
        Animal.all_objects.filter(pk=animal_indep.pk).update(deleted_at=earlier_time)
        animal_indep.refresh_from_db()

        self.assertTrue(animal_indep.is_deleted)
        self.assertEqual(animal_indep.deleted_at, earlier_time)
        self.assertFalse(animal_cascade.is_deleted)

        # 2. Soft-delete client (and cascade to active animal_cascade)
        self.sample_client.soft_delete()
        animal_cascade.refresh_from_db()
        animal_indep.refresh_from_db()

        self.assertTrue(self.sample_client.is_deleted)
        self.assertTrue(animal_cascade.is_deleted)
        self.assertEqual(animal_cascade.deleted_at, self.sample_client.deleted_at)
        # animal_indep's deleted_at was NOT modified and remains earlier_time
        self.assertEqual(animal_indep.deleted_at, earlier_time)

        # 3. Restore client
        self.sample_client.restore()
        animal_cascade.refresh_from_db()
        animal_indep.refresh_from_db()

        self.assertFalse(self.sample_client.is_deleted)
        # animal_cascade was deleted with the client, so it is restored:
        self.assertFalse(animal_cascade.is_deleted)
        self.assertIsNone(animal_cascade.deleted_at)
        # animal_indep was deleted independently beforehand, so it must REMAIN deleted:
        self.assertTrue(animal_indep.is_deleted)
        self.assertEqual(animal_indep.deleted_at, earlier_time)

    def test_file_deletion_aborted_on_transaction_rollback(self):
        """When an animal deletion transaction is rolled back, the physical photo is preserved on disk."""
        import os
        from django.db import transaction
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.patients.models import Animal

        photo = SimpleUploadedFile("rollback_test.png", b"important photo content", content_type="image/png")
        animal = Animal.objects.create(name="سيمبا", client=self.sample_client, photo=photo)
        photo_path = animal.photo.path
        self.assertTrue(os.path.exists(photo_path))

        try:
            with transaction.atomic():
                animal.delete()
                raise RuntimeError("Simulated transaction failure to trigger rollback")
        except RuntimeError:
            pass

        # Photo still exists on disk because on_commit never executed
        self.assertTrue(os.path.exists(photo_path))
        # Clean up
        if os.path.exists(photo_path):
            os.remove(photo_path)

    def test_client_soft_delete_cascades_to_appointments_and_resets_reminders(self):
        """Soft-deleting a Client cascades down to Animal and Appointments, resetting CONVERTED reminders to PENDING."""
        import datetime
        from apps.patients.models import Animal
        from apps.appointments.models import Appointment
        from apps.reminders.models import Reminder

        animal = Animal.objects.create(name="بسبوس", client=self.sample_client)
        appt = Appointment.objects.create(
            animal=animal,
            doctor=self.admin_user,
            date=datetime.date(2026, 9, 25),
            time=datetime.time(12, 0),
            created_by=self.admin_user,
        )
        reminder = Reminder.objects.create(
            animal=animal,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=datetime.date(2026, 9, 25),
            status=Reminder.Status.CONVERTED,
            converted_appointment=appt,
        )

        self.sample_client.soft_delete()

        animal.refresh_from_db()
        appt.refresh_from_db()
        reminder.refresh_from_db()

        self.assertTrue(self.sample_client.is_deleted)
        self.assertTrue(animal.is_deleted)
        self.assertTrue(appt.is_deleted)
        self.assertEqual(animal.deleted_at, self.sample_client.deleted_at)
        self.assertEqual(appt.deleted_at, self.sample_client.deleted_at)
        self.assertEqual(reminder.status, Reminder.Status.PENDING)
        self.assertIsNone(reminder.converted_appointment)

    def test_client_restore_cascades_selectivity_to_appointments(self):
        """Restoring a client restores cascade-deleted animals and appointments, preserving independently deleted ones."""
        import datetime
        from django.utils import timezone
        from apps.patients.models import Animal
        from apps.appointments.models import Appointment

        animal = Animal.objects.create(name="لولو", client=self.sample_client)
        appt_indep = Appointment.objects.create(
            animal=animal,
            doctor=self.admin_user,
            date=datetime.date(2026, 9, 26),
            time=datetime.time(10, 0),
            created_by=self.admin_user,
        )
        appt_cascade = Appointment.objects.create(
            animal=animal,
            doctor=self.admin_user,
            date=datetime.date(2026, 9, 27),
            time=datetime.time(11, 0),
            created_by=self.admin_user,
        )

        # 1. Soft-delete appt_indep independently earlier
        appt_indep.soft_delete()
        earlier_time = timezone.now() - datetime.timedelta(minutes=15)
        Appointment.all_objects.filter(pk=appt_indep.pk).update(deleted_at=earlier_time)
        appt_indep.refresh_from_db()

        # 2. Soft delete client (and cascade to active animal and active appt_cascade)
        self.sample_client.soft_delete()
        animal.refresh_from_db()
        appt_cascade.refresh_from_db()
        appt_indep.refresh_from_db()

        self.assertTrue(self.sample_client.is_deleted)
        self.assertTrue(animal.is_deleted)
        self.assertTrue(appt_cascade.is_deleted)
        self.assertEqual(appt_cascade.deleted_at, self.sample_client.deleted_at)
        self.assertEqual(appt_indep.deleted_at, earlier_time)

        # 3. Restore client
        self.sample_client.restore()
        animal.refresh_from_db()
        appt_cascade.refresh_from_db()
        appt_indep.refresh_from_db()

        self.assertFalse(self.sample_client.is_deleted)
        self.assertFalse(animal.is_deleted)
        self.assertFalse(appt_cascade.is_deleted)
        self.assertTrue(appt_indep.is_deleted)
        self.assertEqual(appt_indep.deleted_at, earlier_time)

    def test_client_phone_duplicate_warning_and_override(self):
        """Duplicate phone blocked on first submit, allowed through with override flag, correctly excludes self when editing."""
        client_a = Client.objects.create(full_name="العميل الأول", phone="0944112233")
        client_b = Client.objects.create(full_name="العميل الثاني", phone="0944998877")

        # 1. Blocked on first submit when creating with an existing phone
        response = self.client_runner.post(
            reverse("clients:create"),
            {"full_name": "العميل الثالث", "phone": "0944112233"},
        )
        self.assertEqual(Client.objects.filter(full_name="العميل الثالث").count(), 0)

        # 2. Allowed with override flag
        response = self.client_runner.post(
            reverse("clients:create"),
            {"full_name": "العميل الثالث", "phone": "0944112233", "confirm_duplicate_phone": "1"},
        )
        self.assertEqual(Client.objects.filter(full_name="العميل الثالث").count(), 1)

        # 3. Editing client_b without changing its own phone is valid (excludes self)
        response = self.client_runner.post(
            reverse("clients:update", args=[client_b.pk]),
            {"full_name": "العميل الثاني معدل", "phone": "0944998877"},
        )
        client_b.refresh_from_db()
        self.assertEqual(client_b.full_name, "العميل الثاني معدل")

        # 4. Editing client_b to match client_a's phone blocked without override
        response = self.client_runner.post(
            reverse("clients:update", args=[client_b.pk]),
            {"full_name": "العميل الثاني محاولة تكرار", "phone": client_a.phone},
        )
        client_b.refresh_from_db()
        self.assertNotEqual(client_b.full_name, "العميل الثاني محاولة تكرار")

        # 5. Editing client_b with override allowed
        response = self.client_runner.post(
            reverse("clients:update", args=[client_b.pk]),
            {"full_name": "العميل الثاني محاولة تكرار", "phone": client_a.phone, "confirm_duplicate_phone": "1"},
        )
        client_b.refresh_from_db()
        self.assertEqual(client_b.full_name, "العميل الثاني محاولة تكرار")

    def test_client_phone_duplicate_catches_equivalent_formats(self):
        """Phone duplicate check catches differently-formatted-but-equivalent numbers (+963, 09, spaces, dashes)."""
        from apps.clients.forms import ClientForm

        Client.objects.create(full_name="عميل دولي", phone="+963955667788")

        # Submitting with local 09 format and dashes
        form = ClientForm(data={"full_name": "عميل جديد", "phone": "0955-667-788"})
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)
        self.assertIn("عميل دولي", form.errors["phone"][0])

        # Allowed with override
        form_with_override = ClientForm(data={
            "full_name": "عميل جديد",
            "phone": "0955-667-788",
            "confirm_duplicate_phone": "1"
        })
        self.assertTrue(form_with_override.is_valid())

    def test_client_phone_duplicate_ajax_two_step_user_flow(self):
        """Simulate two-step user flow: step 1 returns duplicate_warning=True in JSON, step 2 with override succeeds."""
        existing = Client.objects.create(full_name="عميل سابق", phone="0933445566")

        # Step 1: Initial AJAX submission without override flag
        resp1 = self.client_runner.post(
            reverse("clients:create"),
            {"full_name": "عميل مكرر", "phone": "0933445566"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp1.status_code, 400)
        data1 = resp1.json()
        self.assertFalse(data1["success"])
        self.assertTrue(data1.get("duplicate_warning"))
        self.assertEqual(data1.get("duplicate_field"), "phone")
        self.assertIn("عميل سابق", data1["error"])
        self.assertEqual(Client.objects.filter(full_name="عميل مكرر").count(), 0)

        # Step 2: Second AJAX submission with confirm_duplicate_phone=1
        resp2 = self.client_runner.post(
            reverse("clients:create"),
            {"full_name": "عميل مكرر", "phone": "0933445566", "confirm_duplicate_phone": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertTrue(data2["success"])
        self.assertEqual(Client.objects.filter(full_name="عميل مكرر").count(), 1)

    def test_client_multiple_phone_numbers_creation_and_sync(self):
        """Creating a client with extra phone numbers saves them to ClientPhone and synchronizes on update."""
        from apps.clients.models import ClientPhone

        # Create client with primary and 2 extra phones
        post_data = {
            "full_name": "بشار سليمان",
            "phone": "0933112233",
            "address": "دمشق",
            "notes": "عميل بأكثر من رقم",
            "extra_phones": ["0944223344", "0955334455"],
            "extra_labels": ["واتساب", "عمل"],
        }
        response = self.client_runner.post(reverse("clients:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        client = Client.objects.filter(phone="0933112233").first()
        self.assertIsNotNone(client)
        self.assertEqual(client.phone_numbers.count(), 3)
        self.assertEqual(client.secondary_phones.count(), 2)

        primary_rec = client.phone_numbers.filter(is_primary=True).first()
        self.assertEqual(primary_rec.phone, "0933112233")
        self.assertEqual(primary_rec.label, "أساسي")

        extra_phones = list(client.secondary_phones.values_list("phone", "label"))
        self.assertIn(("0944223344", "واتساب"), extra_phones)
        self.assertIn(("0955334455", "عمل"), extra_phones)

        # Update client: remove one extra phone and update primary
        update_data = {
            "full_name": "بشار سليمان معدل",
            "phone": "0933112233",
            "address": "دمشق",
            "notes": "ملاحظة معدلة",
            "extra_phones": ["0944223344"],  # removed 0955334455
            "extra_labels": ["واتساب معدل"],
        }
        up_response = self.client_runner.post(reverse("clients:update", args=[client.pk]), data=update_data)
        self.assertEqual(up_response.status_code, 302)

        client.refresh_from_db()
        self.assertEqual(client.secondary_phones.count(), 1)
        self.assertEqual(client.secondary_phones.first().phone, "0944223344")
        self.assertEqual(client.secondary_phones.first().label, "واتساب معدل")

    def test_search_client_by_secondary_phone(self):
        """Search query matches both primary and secondary phone numbers."""
        from apps.clients.models import ClientPhone

        client = Client.objects.create(full_name="مازن درويش", phone="0966111222")
        ClientPhone.objects.create(client=client, phone="0966111222", is_primary=True, label="أساسي")
        ClientPhone.objects.create(client=client, phone="0999887766", is_primary=False, label="واتساب")

        # Search by secondary phone
        search_res = self.client_runner.get(reverse("clients:list"), {"q": "0999887766"})
        self.assertEqual(search_res.status_code, 200)
        self.assertContains(search_res, "مازن درويش")

    def test_client_soft_delete_and_restore_cascades_to_phones(self):
        """Soft deleting a client cascades to its ClientPhone records and restoring recovers them."""
        from apps.clients.models import ClientPhone

        client = Client.objects.create(full_name="هاني خالد", phone="0944001122")
        p1 = ClientPhone.objects.create(client=client, phone="0944001122", is_primary=True, label="أساسي")
        p2 = ClientPhone.objects.create(client=client, phone="0988001122", is_primary=False, label="عمل")

        client.soft_delete()
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(client.is_deleted)
        self.assertTrue(p1.is_deleted)
        self.assertTrue(p2.is_deleted)

        client.restore()
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertFalse(client.is_deleted)
        self.assertFalse(p1.is_deleted)
        self.assertFalse(p2.is_deleted)




