import re
from django.core.exceptions import ValidationError


def validate_phone_number(value: str) -> str:
    """
    Validates phone numbers according to Syrian clinic rules:
    - If Syrian local number: Must be exactly 10 digits and strictly start with '09' (e.g. 09xxxxxxxx).
    - If Syrian international number (+963 or 00963): Must have 9 digits after country code starting with 9.
    - If non-Syrian / International: Must include the international prefix (+ or 00) followed by valid country code and digits (7 to 15 digits total).
    
    Returns the cleaned phone number or raises ValidationError.
    """
    if not value:
        raise ValidationError("رقم الهاتف مطلوب.")

    raw_phone = str(value).strip()
    
    # Remove spacing and formatting characters
    cleaned = re.sub(r"[\s\-\(\)]", "", raw_phone)

    if not cleaned:
        raise ValidationError("يرجى إدخال رقم هاتف صالح.")

    # 1. Syrian Local Format: starts with '09'
    if cleaned.startswith("09"):
        if not re.match(r"^09\d{8}$", cleaned):
            raise ValidationError(
                "رقم الهاتف السوري يجب أن يتكون من 10 أرقام حصراً ويبدأ بـ 09 (مثال: 0935123456)."
            )
        return cleaned

    # 2. Syrian International Format: starts with '+963' or '00963'
    if cleaned.startswith("+963") or cleaned.startswith("00963"):
        prefix_len = 4 if cleaned.startswith("+963") else 5
        digits_after = cleaned[prefix_len:]
        if not re.match(r"^9\d{8}$", digits_after):
            raise ValidationError(
                "رقم الهاتف السوري بالصيغة الدولية يجب أن يتكون من رمز الدولة متبوعاً بـ 9 أرقام تبدأ بـ 9 (مثال: +963935123456)."
            )
        return cleaned

    # 3. Non-Syrian / International Format: MUST start with '+' or '00'
    if cleaned.startswith("+"):
        if not re.match(r"^\+\d{7,15}$", cleaned):
            raise ValidationError(
                "رقم الهاتف الدولي يجب أن يبدأ بـ + متبوعاً بكود الدولة والرقم (بين 7 و 15 خانة)."
            )
        return cleaned
    elif cleaned.startswith("00"):
        if not re.match(r"^00\d{7,15}$", cleaned):
            raise ValidationError(
                "رقم الهاتف الدولي يجب أن يبدأ بـ 00 متبوعاً بكود الدولة والرقم (بين 7 و 15 خانة)."
            )
        return cleaned
    else:
        # Non-Syrian number without international prefix
        raise ValidationError(
            "الأرقام غير السورية يجب أن تتضمن الرمز والبادئة الدولية (مثال: +961... أو 00966...)، أو إذا كان الرقم سورياً فيجب أن يبدأ بـ 09 ويتكون من 10 أرقام."
        )
