import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import PasswordRecoverySettings

RECOVERY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_RECOVERY_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
SESSION_RECOVERY_CODE_KEY = "pawfect_pending_recovery_code"


def generate_recovery_code() -> str:
    """Readable clinic recovery code, e.g. PC-7K3M-9Q2H."""
    chunk = lambda: "".join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(4))
    return f"PC-{chunk()}-{chunk()}"


def normalize_recovery_code(raw: str) -> str:
    if not raw:
        return ""
    cleaned = "".join(ch for ch in raw.strip().upper() if ch.isalnum())
    if cleaned.startswith("PC") and len(cleaned) == 10:
        return f"PC-{cleaned[2:6]}-{cleaned[6:10]}"
    return raw.strip().upper()


def recovery_code_file_path() -> Path:
    override = getattr(settings, "BACKUP_LOCAL_DIR", None)
    if override:
        return Path(override).parent / "PASSWORD_RECOVERY_CODE.txt"
    return Path(settings.BASE_DIR) / "backups" / "PASSWORD_RECOVERY_CODE.txt"


def write_recovery_code_file(code: str) -> Path:
    path = recovery_code_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_on = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    content = (
        "================================================================================\n"
        "   PAWFECT CLINIC — رمز استعادة كلمة المرور (Password Recovery Code)\n"
        "================================================================================\n\n"
        "احفظ هذا الرمز في مكان آمن خارج جهاز العيادة (ورقة مطبوعة أو USB).\n"
        "يُستخدم من صفحة تسجيل الدخول عند نسيان كلمة المرور.\n\n"
        f"PASSWORD RECOVERY CODE:\n{code}\n\n"
        f"GENERATED ON: {generated_on}\n"
        "================================================================================\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def issue_new_recovery_code(config=None) -> str:
    """Generate, hash, persist, and write the clinic recovery code. Returns plaintext once."""
    code = generate_recovery_code()
    config = config or PasswordRecoverySettings.get_settings()
    config.recovery_code_hash = make_password(normalize_recovery_code(code))
    config.failed_attempts = 0
    config.locked_until = None
    config.save(update_fields=["recovery_code_hash", "failed_attempts", "locked_until", "updated_at"])
    write_recovery_code_file(code)
    return code


def is_recovery_configured(config=None) -> bool:
    config = config or PasswordRecoverySettings.get_settings()
    return bool(config.recovery_code_hash)


def recovery_lockout_remaining(config=None):
    config = config or PasswordRecoverySettings.get_settings()
    if config.locked_until and timezone.now() < config.locked_until:
        remaining = config.locked_until - timezone.now()
        minutes = int(remaining.total_seconds() // 60)
        if remaining.total_seconds() % 60:
            minutes += 1
        return max(1, minutes)
    return 0


def verify_recovery_code(raw_code: str, config=None) -> tuple[bool, str]:
    """
    Constant-style verification of the clinic recovery code with lockout.
    Returns (ok, error_message).
    """
    config = config or PasswordRecoverySettings.get_settings()
    if not config.recovery_code_hash:
        return False, "رمز الاستعادة غير مُعد بعد. سجّل دخول المدير مرة واحدة أو أعد توليد الرمز من إدارة المستخدمين."

    remaining_lock = recovery_lockout_remaining(config)
    if remaining_lock:
        return False, f"تم إيقاف محاولات الاستعادة مؤقتاً. أعد المحاولة بعد {remaining_lock} دقيقة."

    submitted = normalize_recovery_code(raw_code)
    if submitted and check_password(submitted, config.recovery_code_hash):
        config.failed_attempts = 0
        config.locked_until = None
        config.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        return True, ""

    config.failed_attempts = (config.failed_attempts or 0) + 1
    if config.failed_attempts >= MAX_RECOVERY_ATTEMPTS:
        config.locked_until = timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
        config.failed_attempts = 0
        config.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        return False, f"تم إيقاف محاولات الاستعادة مؤقتاً لمدة {LOCKOUT_MINUTES} دقيقة بعد محاولات خاطئة متكررة."

    config.save(update_fields=["failed_attempts", "updated_at"])
    return False, "اسم المستخدم أو رمز الاستعادة غير صحيح."
