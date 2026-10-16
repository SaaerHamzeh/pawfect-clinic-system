import json
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.settings.models import AnimalSpecies, VisitServiceCatalogItem, VaccineCatalogItem

User = get_user_model()


class SetupWizardTests(TestCase):
    def setUp(self):
        self.client = TestClient()
        # Ensure no users initially for clean setup test
        User.objects.all().delete()

    def test_setup_middleware_redirects_when_no_admin(self):
        """When no admin exists, accessing any normal page redirects to /setup/."""
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("setup:wizard")))

    def test_wizard_page_renders_successfully(self):
        """GET /setup/ renders successfully when no admin exists."""
        response = self.client.get(reverse("setup:wizard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "معالج الإعداد الأولي للعيادة")
        self.assertContains(response, "الخطوة 1: إنشاء حساب مدير النظام الأساسي")
        self.assertContains(response, "الخطوة 2: إضافة مستخدمي العيادة")
        self.assertContains(response, "الخطوة 3: تخصيص الخدمات السريرية")

    def test_setup_validation_error_on_mismatch_password(self):
        """Submitting mismatched passwords returns validation error."""
        payload = {
            "admin": {
                "username": "admin_test",
                "first_name": "مدير العيادة",
                "last_name": "الأول",
                "password": "password123",
                "password_confirm": "password999",
            },
            "users": [],
            "customizations": {},
        }
        response = self.client.post(
            reverse("setup:complete"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("غير متطابقين", response.json()["error"])

    def test_complete_setup_flow_success(self):
        """Full setup flow creates Admin, extra users, and applies customizations."""
        payload = {
            "admin": {
                "username": "super_admin",
                "first_name": "د. سامر",
                "last_name": "المهندس",
                "password": "strongPassword123",
                "password_confirm": "strongPassword123",
            },
            "users": [
                {
                    "username": "dr_nour",
                    "first_name": "د. نور",
                    "role": "VET",
                    "password": "vetPassword123",
                },
                {
                    "username": "reception_sara",
                    "first_name": "سارة الاستقبال",
                    "role": "STAFF",
                    "password": "staffPassword123",
                },
            ],
            "customizations": {
                "active_species": ["قطة", "كلب"],
                "new_species": ["سلحفاة"],
                "active_services": ["فحص سريري شامل"],
                "new_services": ["تحليل دم شامل"],
                "active_vaccines": [],
                "new_vaccines": ["لقاح تنفسي"],
            },
        }

        response = self.client.post(
            reverse("setup:complete"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["redirect_url"], reverse("accounts:recovery_code"))
        self.assertTrue(data.get("recovery_code", "").startswith("PC-"))

        # 1. Verify Admin was created with full superuser privileges
        admin_user = User.objects.filter(username="super_admin").first()
        self.assertIsNotNone(admin_user)
        self.assertEqual(admin_user.role, User.Role.ADMIN)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)
        self.assertEqual(admin_user.first_name, "د. سامر")

        # 2. Verify Additional users created
        vet_user = User.objects.filter(username="dr_nour").first()
        self.assertIsNotNone(vet_user)
        self.assertEqual(vet_user.role, User.Role.VET)

        staff_user = User.objects.filter(username="reception_sara").first()
        self.assertIsNotNone(staff_user)
        self.assertEqual(staff_user.role, User.Role.STAFF)

        # 3. Verify Customizations
        self.assertTrue(AnimalSpecies.objects.filter(name="سلحفاة", is_active=True).exists())
        self.assertTrue(VisitServiceCatalogItem.objects.filter(name="تحليل دم شامل", is_active=True).exists())
        self.assertTrue(VaccineCatalogItem.objects.filter(name="لقاح تنفسي", is_active=True).exists())

        # 4. Verify /setup/ is now locked since admin exists
        follow_response = self.client.get(reverse("setup:wizard"))
        self.assertEqual(follow_response.status_code, 302)
