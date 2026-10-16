from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from .utils import (
    generate_license_token,
    get_machine_id,
    is_system_licensed,
    save_license_token,
    verify_license_token,
)


class LicensingUtilsTest(SimpleTestCase):
    def test_machine_id_format(self):
        """Machine ID should follow the PAWF-XXXX-XXXX-XXXX-XXXX format."""
        mid = get_machine_id()
        self.assertTrue(mid.startswith("PAWF-"))
        parts = mid.split("-")
        self.assertEqual(len(parts), 5)
        for part in parts[1:]:
            self.assertEqual(len(part), 4)

    def test_generate_and_verify_valid_token(self):
        """A validly generated token should verify successfully."""
        mid = "PAWF-1111-2222-3333-4444"
        token = generate_license_token(mid, client_name="Vet Hope", plan="LIFETIME")
        valid, msg, payload = verify_license_token(token, target_machine_id=mid)

        self.assertTrue(valid)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["m"], mid)
        self.assertEqual(payload["c"], "Vet Hope")
        self.assertEqual(payload["p"], "LIFETIME")

    def test_reject_machine_mismatch(self):
        """A token generated for Laptop A must be rejected on Laptop B."""
        laptop_a = "PAWF-AAAA-AAAA-AAAA-AAAA"
        laptop_b = "PAWF-BBBB-BBBB-BBBB-BBBB"

        token = generate_license_token(laptop_a, client_name="Vet Hope")
        valid, msg, payload = verify_license_token(token, target_machine_id=laptop_b)

        self.assertFalse(valid)
        self.assertIn("مخصص لجهاز آخر", msg)
        self.assertIsNone(payload)

    def test_reject_tampered_token(self):
        """Tampering with token content or signature must fail verification."""
        mid = "PAWF-1111-2222-3333-4444"
        token = generate_license_token(mid, client_name="Vet Hope")

        # Corrupt the token string
        tampered = token[:-4] + "XXXX"
        valid, msg, payload = verify_license_token(tampered, target_machine_id=mid)
        self.assertFalse(valid)

    def test_expiration_logic(self):
        """Expired licenses must fail, while future-dated licenses must pass."""
        mid = "PAWF-1111-2222-3333-4444"

        # Past expiration date
        past_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        expired_token = generate_license_token(mid, expires_at=past_date)
        valid, msg, _ = verify_license_token(expired_token, target_machine_id=mid)
        self.assertFalse(valid)
        self.assertIn("انتهت صلاحية", msg)

        # Future expiration date
        future_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        valid_token = generate_license_token(mid, expires_at=future_date)
        valid, msg, _ = verify_license_token(valid_token, target_machine_id=mid)
        self.assertTrue(valid)


class LicensingViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.activate_url = reverse("licensing:activate")

    def test_activate_page_loads(self):
        """Activation page should load with 200 and display the machine ID."""
        response = self.client.get(self.activate_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, get_machine_id())

    def test_submit_invalid_license_key(self):
        """Submitting an invalid license key should render an error."""
        response = self.client.post(self.activate_url, {"license_key": "INVALID-KEY-123"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تنسيق مفتاح الترخيص غير صالح")

    def test_submit_valid_license_key_fresh_setup(self):
        """On a fresh installation without Admin, successful activation redirects to Setup Wizard."""
        current_mid = get_machine_id()
        valid_key = generate_license_token(current_mid, client_name="Test Clinic")

        with patch("apps.licensing.utils.get_license_file_path") as mock_path:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                mock_path.return_value = Path(tmp.name)

            response = self.client.post(self.activate_url, {"license_key": valid_key})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("setup:wizard"))

    def test_submit_valid_license_key_with_existing_admin(self):
        """When an Admin already exists, successful activation redirects to Dashboard."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create_user(
            username="admin_test",
            password="password123",
            role=User.Role.ADMIN,
            is_active=True,
        )

        current_mid = get_machine_id()
        valid_key = generate_license_token(current_mid, client_name="Test Clinic")

        with patch("apps.licensing.utils.get_license_file_path") as mock_path:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                mock_path.return_value = Path(tmp.name)

            response = self.client.post(self.activate_url, {"license_key": valid_key})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("core:dashboard"))
