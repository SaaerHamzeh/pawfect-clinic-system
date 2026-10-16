import base64
import hashlib
import hmac
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from django.conf import settings

# Master secret key used for signing licenses (Offline HMAC-SHA256)
DEFAULT_MASTER_SECRET = "pawfect-clinic-v1-offline-hardware-master-secret-2026"


def get_master_secret() -> str:
    """Return the master secret for signing and verifying licenses."""
    return os.environ.get("PAWFECT_LICENSE_SECRET", DEFAULT_MASTER_SECRET)


import functools


@functools.lru_cache(maxsize=1)
def get_raw_machine_guid() -> str:
    """
    Extract immutable system hardware identifier.
    Primary: Motherboard Hardware UUID (Burned in BIOS chip - survives OS formatting and Windows re-installation).
    Secondary: Windows Cryptography Registry GUID.
    Fallback: Hardware MAC / Node UUID.
    """
    if sys.platform == "win32":
        # 1. Primary: Motherboard Hardware UUID
        try:
            import subprocess

            cmd = [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID",
            ]
            mb_uuid = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=4).strip()
            # Verify it's a real valid UUID and not empty or placeholder like 00000000-0000...
            cleaned = mb_uuid.replace("-", "").lower()
            if mb_uuid and len(mb_uuid) >= 32 and not (set(cleaned) <= {"0"} or set(cleaned) <= {"f"}):
                return mb_uuid.upper()
        except Exception:
            pass

        # 2. Secondary: Windows Cryptography Registry GUID
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if guid:
                return str(guid).strip()
        except Exception:
            pass

    # 3. Fallback for non-windows environments / VMs
    import uuid

    return str(uuid.getnode())


def get_machine_id(raw_guid: str | None = None) -> str:
    """
    Generate a human-readable, hardware-bound Machine ID.
    Format: PAWF-XXXX-XXXX-XXXX-XXXX
    """
    if not raw_guid:
        raw_guid = get_raw_machine_guid()

    seed = f"PAWFECT-HW-SEED:{raw_guid}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
    return f"PAWF-{digest[:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"


def generate_license_token(
    machine_id: str,
    client_name: str = "Pawfect Clinic",
    plan: str = "LIFETIME",
    expires_at: str | None = None,
    secret: str | None = None,
) -> str:
    """
    Generate a cryptographically signed license token for a specific Machine ID.
    This is run by the developer to provide an activation key to the client.
    """
    secret = secret or get_master_secret()
    clean_machine_id = machine_id.strip().upper()

    payload = {
        "m": clean_machine_id,
        "c": client_name.strip(),
        "p": plan.upper(),
        "e": expires_at.strip() if expires_at else None,
        "t": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    # Deterministic JSON serialization for HMAC signature
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    token_dict = {
        "v": 1,
        "data": payload,
        "sig": sig,
    }

    raw_token = json.dumps(token_dict, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw_token.encode("utf-8")).decode("utf-8")


def verify_license_token(
    token_str: str,
    target_machine_id: str | None = None,
    secret: str | None = None,
) -> tuple[bool, str, dict | None]:
    """
    Verify a license token:
    1. Valid Base64 & JSON structure
    2. Valid HMAC-SHA256 signature against secret
    3. Matches target Machine ID
    4. Not expired (if expires_at is present)

    Returns: (is_valid: bool, message: str, payload_data: dict | None)
    """
    secret = secret or get_master_secret()
    target_machine_id = target_machine_id or get_machine_id()

    token_str = token_str.strip()
    if not token_str:
        return False, "مفتاح الترخيص فارغ.", None

    try:
        decoded_bytes = base64.urlsafe_b64decode(token_str.encode("utf-8"))
        token_dict = json.loads(decoded_bytes.decode("utf-8"))
        payload = token_dict.get("data", {})
        given_sig = token_dict.get("sig", "")
    except Exception:
        return False, "تنسيق مفتاح الترخيص غير صالح.", None

    # Verify cryptographic signature
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(given_sig, expected_sig):
        return False, "مفتاح الترخيص غير معتمد أو تم التعديل عليه.", None

    # Verify Machine ID binding
    token_machine = payload.get("m", "").strip().upper()
    if token_machine != target_machine_id.strip().upper():
        return False, f"مفتاح الترخيص مخصص لجهاز آخر ({token_machine}) ولا يطابق هذا الجهاز.", None

    # Verify expiration date if specified
    expires_at = payload.get("e")
    if expires_at:
        try:
            exp_date = datetime.strptime(expires_at, "%Y-%m-%d").date()
            if date.today() > exp_date:
                return False, f"انتهت صلاحية هذا الترخيص بتاريخ {expires_at}.", None
        except ValueError:
            return False, "تاريخ انتهاء الترخيص في المفتاح غير صالح.", None

    return True, "تم التحقق من الترخيص بنجاح.", payload


def get_license_file_path() -> Path:
    """Return the filesystem path to pawfect.lic in BASE_DIR."""
    return Path(settings.BASE_DIR) / "pawfect.lic"


def is_system_licensed() -> tuple[bool, str, dict | None]:
    """
    Check if the current host machine is properly licensed.
    Returns: (is_licensed, status_message, license_data)
    """
    # Environment bypass flag (strictly for automated test suites)
    if os.environ.get("PAWFECT_SKIP_LICENSE") == "1":
        return True, "Test bypass active", {"m": "TEST-DEVICE", "p": "TEST_BYPASS"}

    lic_file = get_license_file_path()
    if not lic_file.exists():
        return False, "لم يتم العثور على ملف الترخيص. النظام بحاجة إلى تفعيل.", None

    try:
        token_str = lic_file.read_text(encoding="utf-8").strip()
    except Exception as e:
        return False, f"تعذر قراءة ملف الترخيص: {e}", None

    return verify_license_token(token_str)


def save_license_token(token_str: str) -> tuple[bool, str, dict | None]:
    """
    Verify and persist the license token to pawfect.lic.
    """
    valid, msg, payload = verify_license_token(token_str)
    if not valid:
        return False, msg, None

    try:
        lic_file = get_license_file_path()
        lic_file.write_text(token_str.strip(), encoding="utf-8")
        return True, "تم تفعيل البرنامج وحفظ الترخيص بنجاح.", payload
    except Exception as e:
        return False, f"تعذر حفظ ملف الترخيص: {e}", None
