from django.test import TestCase, Client as TestClient
from django.urls import reverse
from apps.accounts.models import User
from apps.clients.models import Client
from apps.patients.models import Animal
from apps.patients.forms import AnimalForm
from apps.audit.models import AuditLog


class PatientViewsAndBusinessRulesTests(TestCase):
    def setUp(self):
        self.client_runner = TestClient()
        self.admin_user = User.objects.create_superuser(
            username="admin_user",
            password="password123",
            role=User.Role.ADMIN,
        )
        self.client_runner.login(username="admin_user", password="password123")

        self.owner = Client.objects.create(
            full_name="رندة خالد",
            phone="0944555666",
            address="دمشق - الشعلان",
        )

        self.animal_cat = Animal.objects.create(
            name="مشمش",
            species=Animal.Species.CAT,
            breed="شيرازي",
            gender=Animal.Gender.MALE,
            weight=3.8,
            color="مشمشي فاتح",
            client=self.owner,
        )

        self.animal_dog = Animal.objects.create(
            name="روكي",
            species=Animal.Species.DOG,
            breed="هاسكي",
            gender=Animal.Gender.MALE,
            weight=18.5,
            color="رمادي وأبيض",
            client=self.owner,
        )

    def test_patients_list_view_and_species_filter(self):
        response = self.client_runner.get(reverse("patients:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مشمش")
        self.assertContains(response, "روكي")

        # Filter by CAT species
        cat_res = self.client_runner.get(reverse("patients:list"), {"species": "CAT"})
        self.assertEqual(cat_res.status_code, 200)
        self.assertContains(cat_res, "مشمش")
        self.assertNotContains(cat_res, "روكي")

        # Filter by DOG species
        dog_res = self.client_runner.get(reverse("patients:list"), {"species": "DOG"})
        self.assertEqual(dog_res.status_code, 200)
        self.assertContains(dog_res, "روكي")
        self.assertNotContains(dog_res, "مشمش")

    def test_patient_detail_view(self):
        response = self.client_runner.get(
            reverse("patients:detail", args=[self.animal_cat.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مشمش")
        self.assertContains(response, "رندة خالد")
        self.assertContains(response, "3.8")

    def test_patient_create_and_audit_log(self):
        post_data = {
            "name": "بيلا",
            "species": Animal.Species.CAT,
            "breed": "سيامي",
            "gender": Animal.Gender.FEMALE,
            "weight": "2.9",
            "color": "بيج وأطراف بنية",
            "client": str(self.owner.pk),
            "notes": "حيوان أليف جديد",
        }
        response = self.client_runner.post(reverse("patients:create"), data=post_data)
        self.assertEqual(response.status_code, 302)

        created_animal = Animal.objects.filter(name="بيلا").first()
        self.assertIsNotNone(created_animal)
        self.assertEqual(created_animal.client, self.owner)

        # Check Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                entity_id=str(created_animal.pk),
            ).exists()
        )

    def test_patient_update_and_audit_log(self):
        post_data = {
            "name": "مشمش المعدل",
            "species": Animal.Species.CAT,
            "breed": "شيرازي نقي",
            "gender": Animal.Gender.MALE,
            "weight": "4.1",
            "color": "مشمشي",
            "client": str(self.owner.pk),
        }
        response = self.client_runner.post(
            reverse("patients:update", args=[self.animal_cat.pk]), data=post_data
        )
        self.assertEqual(response.status_code, 302)

        self.animal_cat.refresh_from_db()
        self.assertEqual(self.animal_cat.name, "مشمش المعدل")
        self.assertEqual(float(self.animal_cat.weight), 4.1)

        # Check Audit Log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                entity_id=str(self.animal_cat.pk),
            ).exists()
        )

    def test_patient_soft_delete_and_restore(self):
        # Soft delete
        del_response = self.client_runner.post(
            reverse("patients:delete", args=[self.animal_cat.pk])
        )
        self.assertEqual(del_response.status_code, 302)

        self.animal_cat.refresh_from_db()
        self.assertTrue(self.animal_cat.is_deleted)
        self.assertFalse(Animal.objects.alive().filter(pk=self.animal_cat.pk).exists())
        self.assertTrue(Animal.objects.deleted_only().filter(pk=self.animal_cat.pk).exists())

        # Check Audit Log for DELETE
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE,
                entity_id=str(self.animal_cat.pk),
            ).exists()
        )

        # Restore
        restore_response = self.client_runner.post(
            reverse("patients:restore", args=[self.animal_cat.pk])
        )
        self.assertEqual(restore_response.status_code, 302)

        self.animal_cat.refresh_from_db()
        self.assertFalse(self.animal_cat.is_deleted)

        # Check Audit Log for RESTORE
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.RESTORE,
                entity_id=str(self.animal_cat.pk),
            ).exists()
        )

    def test_unique_7_digit_animal_id_generation(self):
        """Test that animal_id is generated sequentially as 7-digits (0000001, 0000002) and is immutable on edit."""
        a1 = Animal.objects.create(
            name="حيوان 1",
            species=Animal.Species.CAT,
            client=self.owner,
        )
        self.assertTrue(len(a1.animal_id) == 7)
        self.assertTrue(a1.animal_id.isdigit())

        a2 = Animal.objects.create(
            name="حيوان 2",
            species=Animal.Species.DOG,
            client=self.owner,
        )
        self.assertTrue(len(a2.animal_id) == 7)
        self.assertTrue(a2.animal_id.isdigit())
        self.assertEqual(int(a2.animal_id), int(a1.animal_id) + 1)

        # Ensure animal_id is immutable on subsequent saves
        original_id = a1.animal_id
        a1.name = "اسم معدل"
        a1.save()
        a1.refresh_from_db()
        self.assertEqual(a1.animal_id, original_id)

    def test_search_by_animal_id(self):
        """Test that search query filters by animal_id."""
        response = self.client_runner.get(reverse("patients:list"), {"q": self.animal_cat.animal_id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.animal_cat.name)

    def test_patient_quick_search_api(self):
        """Test JSON autocomplete search endpoint supporting unique animal_id, name, owner, and phone."""
        self.client_runner.force_login(self.admin_user)

        # 1. Search by unique animal_id with # prefix
        resp = self.client_runner.get(reverse("patients:api_search"), {"q": f"#{self.animal_cat.animal_id}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("results", data)
        self.assertTrue(any(item["id"] == self.animal_cat.pk for item in data["results"]))

        # 2. Search by owner phone
        resp_phone = self.client_runner.get(reverse("patients:api_search"), {"q": self.owner.phone})
        self.assertEqual(resp_phone.status_code, 200)
        data_phone = resp_phone.json()
        self.assertTrue(len(data_phone["results"]) > 0)

        # 3. Empty query returns empty results
        resp_empty = self.client_runner.get(reverse("patients:api_search"), {"q": ""})
        self.assertEqual(resp_empty.status_code, 200)
        self.assertEqual(resp_empty.json()["results"], [])

    def test_direct_animal_hard_delete_physically_deletes_media_files(self):
        """Test that direct animal hard deletion physically removes photo and attachments from disk."""
        import os
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.clinical.models import FileAttachment

        photo = SimpleUploadedFile("direct_pet_photo.png", b"test direct photo", content_type="image/png")
        animal = Animal.objects.create(name="شمس", client=self.owner, photo=photo)
        photo_path = animal.photo.path
        self.assertTrue(os.path.exists(photo_path))

        att = SimpleUploadedFile("direct_lab.pdf", b"test lab report", content_type="application/pdf")
        attachment = FileAttachment.objects.create(animal=animal, file=att, file_name="direct_lab.pdf", file_size=15)
        att_path = attachment.file.path
        self.assertTrue(os.path.exists(att_path))

        # Soft delete first
        animal.soft_delete()

        # Hard delete directly
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_runner.post(reverse("patients:hard_delete", args=[animal.pk]))
        self.assertEqual(resp.status_code, 302)

        # Confirm files removed from disk
        self.assertFalse(os.path.exists(photo_path))
        self.assertFalse(os.path.exists(att_path))

    def test_animal_soft_delete_cascades_to_appointments_and_resets_reminders(self):
        """Soft-deleting an Animal cascades soft-delete to its active appointments and resets CONVERTED reminders to PENDING."""
        import datetime
        from apps.appointments.models import Appointment
        from apps.reminders.models import Reminder

        appt = Appointment.objects.create(
            animal=self.animal_cat,
            doctor=self.admin_user,
            date=datetime.date(2026, 9, 20),
            time=datetime.time(10, 0),
            created_by=self.admin_user,
        )
        reminder = Reminder.objects.create(
            animal=self.animal_cat,
            reminder_type=Reminder.ReminderType.CHECKUP,
            due_date=datetime.date(2026, 9, 20),
            status=Reminder.Status.CONVERTED,
            converted_appointment=appt,
        )

        self.animal_cat.soft_delete()

        appt.refresh_from_db()
        reminder.refresh_from_db()

        self.assertTrue(self.animal_cat.is_deleted)
        self.assertTrue(appt.is_deleted)
        self.assertEqual(appt.deleted_at, self.animal_cat.deleted_at)
        self.assertEqual(reminder.status, Reminder.Status.PENDING)
        self.assertIsNone(reminder.converted_appointment)

    def test_animal_restore_selectivity_preserves_independently_deleted_appointments(self):
        """An appointment soft-deleted independently BEFORE its animal was soft-deleted must NOT be restored when the animal is restored."""
        import datetime
        from django.utils import timezone
        from apps.appointments.models import Appointment

        appt_indep = Appointment.objects.create(
            animal=self.animal_cat,
            doctor=self.admin_user,
            date=datetime.date(2026, 9, 21),
            time=datetime.time(10, 0),
            created_by=self.admin_user,
        )
        appt_cascade = Appointment.objects.create(
            animal=self.animal_cat,
            doctor=self.admin_user,
            date=datetime.date(2026, 9, 22),
            time=datetime.time(11, 0),
            created_by=self.admin_user,
        )

        # 1. Soft-delete appt_indep independently 10 minutes prior
        appt_indep.soft_delete()
        earlier_time = timezone.now() - datetime.timedelta(minutes=10)
        Appointment.all_objects.filter(pk=appt_indep.pk).update(deleted_at=earlier_time)
        appt_indep.refresh_from_db()

        self.assertTrue(appt_indep.is_deleted)
        self.assertEqual(appt_indep.deleted_at, earlier_time)
        self.assertFalse(appt_cascade.is_deleted)

        # 2. Soft-delete animal (and cascade to active appt_cascade)
        self.animal_cat.soft_delete()
        appt_cascade.refresh_from_db()
        appt_indep.refresh_from_db()

        self.assertTrue(self.animal_cat.is_deleted)
        self.assertTrue(appt_cascade.is_deleted)
        self.assertEqual(appt_cascade.deleted_at, self.animal_cat.deleted_at)
        self.assertEqual(appt_indep.deleted_at, earlier_time)

        # 3. Restore animal
        self.animal_cat.restore()
        appt_cascade.refresh_from_db()
        appt_indep.refresh_from_db()

        self.assertFalse(self.animal_cat.is_deleted)
        self.assertFalse(appt_cascade.is_deleted)
        self.assertTrue(appt_indep.is_deleted)
        self.assertEqual(appt_indep.deleted_at, earlier_time)

    def test_animal_name_duplicate_warning_and_override_scoped_to_owner(self):
        """Duplicate animal name under same client blocked on first submit, allowed with override, not triggered for different client."""
        # 1. animal_cat ("مشمش") belongs to self.owner
        # Blocked on first submit without override
        response = self.client_runner.post(
            reverse("patients:create"),
            {
                "name": "مشمش",
                "species": Animal.Species.CAT,
                "gender": Animal.Gender.MALE,
                "client": self.owner.pk,
            },
        )
        self.assertEqual(Animal.objects.filter(client=self.owner, name="مشمش").count(), 1)

        # 2. Allowed with override flag
        response = self.client_runner.post(
            reverse("patients:create"),
            {
                "name": "مشمش",
                "species": Animal.Species.CAT,
                "gender": Animal.Gender.MALE,
                "client": self.owner.pk,
                "confirm_duplicate_name": "1",
            },
        )
        self.assertEqual(Animal.objects.filter(client=self.owner, name="مشمش").count(), 2)

        # 3. Same name under a DIFFERENT client should NOT be blocked
        other_client = Client.objects.create(full_name="مالك آخر", phone="0988776655")
        form = AnimalForm(data={
            "name": "مشمش",
            "species": Animal.Species.CAT,
            "gender": Animal.Gender.MALE,
            "client": other_client.pk,
        })
        self.assertTrue(form.is_valid())

        # 4. Editing animal_dog keeping its unique name does NOT trigger duplicate (excludes self)
        form_edit_dog = AnimalForm(
            data={
                "name": "روكي",
                "species": Animal.Species.DOG,
                "gender": Animal.Gender.MALE,
                "client": self.owner.pk,
            },
            instance=self.animal_dog,
        )
        self.assertTrue(form_edit_dog.is_valid())

        # 5. Editing animal_dog to rename to "مشمش" blocked without override
        form_conflict = AnimalForm(
            data={
                "name": "مشمش",
                "species": Animal.Species.DOG,
                "gender": Animal.Gender.MALE,
                "client": self.owner.pk,
            },
            instance=self.animal_dog,
        )
        self.assertFalse(form_conflict.is_valid())
        self.assertIn("name", form_conflict.errors)

        # 6. Editing animal_dog to rename to "مشمش" allowed with override
        form_conflict_override = AnimalForm(
            data={
                "name": "مشمش",
                "species": Animal.Species.DOG,
                "gender": Animal.Gender.MALE,
                "client": self.owner.pk,
                "confirm_duplicate_name": "1",
            },
            instance=self.animal_dog,
        )
        self.assertTrue(form_conflict_override.is_valid())

    def test_animal_duplicate_name_ajax_two_step_user_flow(self):
        """Simulate two-step user flow: step 1 returns duplicate_warning=True in JSON, step 2 with override succeeds."""
        # Step 1: Initial AJAX create with duplicate name "مشمش" for self.owner
        resp1 = self.client_runner.post(
            reverse("patients:create"),
            {
                "name": "مشمش",
                "species": Animal.Species.CAT,
                "gender": Animal.Gender.MALE,
                "client": self.owner.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp1.status_code, 400)
        data1 = resp1.json()
        self.assertFalse(data1["success"])
        self.assertTrue(data1.get("duplicate_warning"))
        self.assertEqual(data1.get("duplicate_field"), "name")
        self.assertIn("مشمش", data1["error"])
        self.assertEqual(Animal.objects.filter(client=self.owner, name="مشمش").count(), 1)

        # Step 2: Resubmit with confirm_duplicate_name=1
        resp2 = self.client_runner.post(
            reverse("patients:create"),
            {
                "name": "مشمش",
                "species": Animal.Species.CAT,
                "gender": Animal.Gender.MALE,
                "client": self.owner.pk,
                "confirm_duplicate_name": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertTrue(data2["success"])
        self.assertEqual(Animal.objects.filter(client=self.owner, name="مشمش").count(), 2)

    def test_patient_update_photo_upload_and_delete(self):
        """Test uploading a photo via camera/gallery and deleting it."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Small 1x1 GIF image
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        photo = SimpleUploadedFile("mishmish.gif", small_gif, content_type="image/gif")

        url = reverse("patients:update_photo", kwargs={"patient_id": self.animal_cat.pk})
        resp = self.client_runner.post(
            url,
            {"photo": photo},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.animal_cat.refresh_from_db()
        self.assertTrue(bool(self.animal_cat.photo))

        # Check AuditLog
        self.assertTrue(
            AuditLog.objects.filter(
                entity_id=str(self.animal_cat.pk),
                action=AuditLog.Action.UPDATE,
            ).exists()
        )

        # Test deleting photo
        del_resp = self.client_runner.post(
            url,
            {"delete_photo": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(del_resp.status_code, 200)
        del_data = del_resp.json()
        self.assertTrue(del_data["success"])
        self.animal_cat.refresh_from_db()
        self.assertFalse(bool(self.animal_cat.photo))

    def test_attachment_preview_and_download_options_rendered(self):
        """Test that file attachments display both preview and download buttons, and FileAttachment detects image and pdf types."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.clinical.models import FileAttachment

        image_att = SimpleUploadedFile("xray_scan.jpg", b"image data", content_type="image/jpeg")
        pdf_att = SimpleUploadedFile("lab_report.pdf", b"pdf data", content_type="application/pdf")

        att1 = FileAttachment.objects.create(animal=self.animal_dog, file=image_att, file_name="xray_scan.jpg", file_size=1024)
        att2 = FileAttachment.objects.create(animal=self.animal_dog, file=pdf_att, file_name="lab_report.pdf", file_size=2048)

        self.assertTrue(att1.is_image)
        self.assertFalse(att1.is_pdf)
        self.assertTrue(att2.is_pdf)
        self.assertFalse(att2.is_image)

        resp = self.client_runner.get(reverse("patients:detail", args=[self.animal_dog.pk]))
        self.assertEqual(resp.status_code, 200)
        # Should contain both معاينة and تحميل buttons for attachments
        self.assertContains(resp, "معاينة")
        self.assertContains(resp, "تحميل")
        self.assertContains(resp, "showFilePreviewModal")

    def test_species_breeds_map_and_form_unification(self):
        """Test AnimalBreed.get_species_breeds_map returns active breeds grouped by species and form handles catalog/custom breeds."""
        from apps.settings.models import AnimalSpecies, AnimalBreed

        # Verify species breeds mapping
        species_map = AnimalBreed.get_species_breeds_map()
        self.assertIsInstance(species_map, dict)
        self.assertIn("CAT", species_map)

        # Create animal with catalog breed
        post_data = {
            "name": "سيمبا اللطيف",
            "species": "CAT",
            "breed": "شيرازي",
            "gender": Animal.Gender.MALE,
            "client": self.owner.pk,
        }
        res = self.client_runner.post(reverse("patients:create"), data=post_data)
        self.assertEqual(res.status_code, 302)
        created_cat = Animal.objects.filter(name="سيمبا اللطيف").first()
        self.assertIsNotNone(created_cat)
        self.assertEqual(created_cat.breed, "شيرازي")

        # Create animal with custom manual breed
        post_data_custom = {
            "name": "روكي الشجاع",
            "species": "DOG",
            "breed": "سلالة مهجنة خاصة",
            "gender": Animal.Gender.MALE,
            "client": self.owner.pk,
        }
        res_custom = self.client_runner.post(reverse("patients:create"), data=post_data_custom)
        self.assertEqual(res_custom.status_code, 302)
        created_dog = Animal.objects.filter(name="روكي الشجاع").first()
        self.assertIsNotNone(created_dog)
        self.assertEqual(created_dog.breed, "سلالة مهجنة خاصة")




