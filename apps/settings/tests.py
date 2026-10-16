from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.settings.models import (
    AnimalSpecies,
    AnimalBreed,
    ClinicalVisitType,
    AppointmentTypeConfig,
    VaccineCatalogItem,
    VisitServiceCatalogItem,
)


class AuditLogsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            password="password123",
            role=User.Role.ADMIN,
        )
        self.client.login(username="admin_test", password="password123")

        # Create a sample audit log
        AuditLog.log(
            user=self.admin_user,
            action=AuditLog.Action.LOGIN,
            entity_type="جلسة مستخدم",
            entity_id=str(self.admin_user.pk),
            description="تسجيل دخول تجريبي",
            ip_address="127.0.0.1",
        )

    def test_audit_logs_view_authenticated(self):
        response = self.client.get(reverse("settings:audit_logs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سجل العمليات")
        self.assertContains(response, "تسجيل دخول تجريبي")

    def test_audit_logs_filtering_by_action(self):
        response = self.client.get(reverse("settings:audit_logs"), {"action": "LOGIN"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تسجيل دخول تجريبي")

        response_empty = self.client.get(reverse("settings:audit_logs"), {"action": "DELETE"})
        self.assertEqual(response_empty.status_code, 200)
        self.assertNotContains(response_empty, "تسجيل دخول تجريبي")


class LookupsAndTaxonomiesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_lookups",
            password="password123",
            role=User.Role.ADMIN,
        )
        self.staff_user = User.objects.create_user(
            username="staff_lookups",
            password="password123",
            role=User.Role.STAFF,
        )
        self.client.login(username="admin_lookups", password="password123")

    def test_lookups_dashboard_admin_access(self):
        """Admin can access lookups dashboard."""
        response = self.client.get(reverse("settings:lookups"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "إدارة القوائم والتصنيفات المخصصة")

    def test_lookups_dashboard_non_admin_forbidden(self):
        """Non-admin user cannot access lookups dashboard."""
        self.client.login(username="staff_lookups", password="password123")
        response = self.client.get(reverse("settings:lookups"))
        self.assertEqual(response.status_code, 403)

    def test_add_and_toggle_species(self):
        """Admin can add a new species and toggle its active state."""
        # Add new species
        response = self.client.post(reverse("settings:save_species"), {
            "name": "سلحفاة",
            "icon": "🐢",
            "order": 10,
        })
        self.assertEqual(response.status_code, 302)
        species = AnimalSpecies.objects.filter(name="سلحفاة").first()
        self.assertIsNotNone(species)
        self.assertTrue(species.is_active)
        self.assertFalse(species.is_system)

        # Toggle status to inactive
        response = self.client.post(reverse("settings:toggle_species", args=[species.pk]))
        self.assertEqual(response.status_code, 302)
        species.refresh_from_db()
        self.assertFalse(species.is_active)

    def test_system_species_protection(self):
        """System species cannot be deleted."""
        cat_species = AnimalSpecies.objects.filter(code="CAT", is_system=True).first()
        if not cat_species:
            cat_species = AnimalSpecies.objects.create(name="قطة", code="CAT", is_system=True)

        response = self.client.post(reverse("settings:delete_species", args=[cat_species.pk]))
        self.assertEqual(response.status_code, 302)
        # Verify it still exists in DB
        self.assertTrue(AnimalSpecies.objects.filter(pk=cat_species.pk).exists())

    def test_custom_species_deletion(self):
        """Custom non-system species can be deleted."""
        custom_species = AnimalSpecies.objects.create(name="قنفذ", icon="🦔", is_system=False)
        response = self.client.post(reverse("settings:delete_species", args=[custom_species.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AnimalSpecies.objects.filter(pk=custom_species.pk, is_deleted=False).exists())

    def test_breeds_crud_and_api(self):
        """Admin can add breeds and fetch them via API."""
        cat_species = AnimalSpecies.objects.filter(code="CAT").first()
        if not cat_species:
            cat_species = AnimalSpecies.objects.create(name="قطة", code="CAT", is_system=True)

        # Add custom breed
        response = self.client.post(reverse("settings:save_breed"), {
            "species_id": cat_species.pk,
            "name": "ماين كون",
            "order": 1,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AnimalBreed.objects.filter(name="ماين كون", species=cat_species).exists())

        # Test API
        api_url = reverse("settings:api_species_breeds", args=[cat_species.pk])
        api_resp = self.client.get(api_url)
        self.assertEqual(api_resp.status_code, 200)
        data = api_resp.json()
        self.assertIn("breeds", data)
        breed_names = [b["name"] for b in data["breeds"]]
        self.assertIn("ماين كون", breed_names)

    def test_visit_type_and_vaccine_catalog_crud(self):
        """Admin can add custom visit types and vaccine catalog items."""
        # Add custom visit type
        response = self.client.post(reverse("settings:save_visit_type"), {
            "name": "جلسة ليزر علاجي",
            "icon": "⚡",
            "color": "#eab308",
            "order": 5,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ClinicalVisitType.objects.filter(name="جلسة ليزر علاجي").exists())

        # Add vaccine
        response = self.client.post(reverse("settings:save_vaccine"), {
            "name": "لقاح اللوكيميا للقطط (FeLV)",
            "default_validity_days": 365,
            "notes": "جرعة سنوية",
            "order": 2,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(VaccineCatalogItem.objects.filter(name="لقاح اللوكيميا للقطط (FeLV)").exists())
