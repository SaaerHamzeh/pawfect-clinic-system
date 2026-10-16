#!/usr/bin/env python
"""
Pawfect Clinic — Developer Offline License Generator
---------------------------------------------------
This tool is strictly for the software author / vendor.
Use this script to generate cryptographically signed hardware-locked licenses
for customer machines without needing any internet connection.

Usage:
  python scripts/generate_license.py --machine PAWF-XXXX-XXXX-XXXX-XXXX --client "Dr. Smith Clinic"
  python scripts/generate_license.py --current --client "Local Dev License"
  python scripts/generate_license.py (Interactive prompt mode)
"""

import argparse
import io
import os
import sys
from pathlib import Path

# Ensure UTF-8 output in Windows Command Prompt / PowerShell
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path so we can import utils directly
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup Django settings minimally if needed
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from apps.licensing.utils import (  # noqa: E402
    generate_license_token,
    get_machine_id,
    verify_license_token,
)


def main():
    parser = argparse.ArgumentParser(
        description="Pawfect Clinic — Offline Hardware License Generator (Developer Tool)"
    )
    parser.add_argument("-m", "--machine", help="Customer Machine ID (e.g. PAWF-XXXX-XXXX-XXXX-XXXX)")
    parser.add_argument("-c", "--client", default="Pawfect Clinic", help="Customer / Clinic Name")
    parser.add_argument("-p", "--plan", default="LIFETIME", help="License plan (LIFETIME, ANNUAL, TRIAL)")
    parser.add_argument("-e", "--expires", help="Expiration date (YYYY-MM-DD), optional")
    parser.add_argument("-o", "--out", help="Write token to a file path (e.g. pawfect.lic)")
    parser.add_argument("--current", action="store_true", help="Generate license for the current host PC")

    args = parser.parse_args()

    machine_id = args.machine
    if args.current:
        machine_id = get_machine_id()
        print(f"[*] Detected Current Host Machine ID: {machine_id}")

    # Interactive mode if machine_id is not provided
    if not machine_id:
        print("=" * 65)
        print("  Pawfect Clinic — Offline Hardware License Generator")
        print("=" * 65)
        try:
            curr_id = get_machine_id()
            print(f"[i] (معرّف هذا الجهاز الحالي: {curr_id})")
        except Exception:
            curr_id = ""

        machine_id = input("\nأدخل رمز جهاز العميل (Machine ID): ").strip()
        if not machine_id:
            print("[!] خطأ: يجب إدخال رمز جهاز العميل.")
            sys.exit(1)

        client_input = input(f"اسم العيادة/العميل [{args.client}]: ").strip()
        if client_input:
            args.client = client_input

        plan_input = input(f"نوع الترخيص (LIFETIME / TRIAL) [{args.plan}]: ").strip()
        if plan_input:
            args.plan = plan_input

        exp_input = input("تاريخ الانتهاء YYYY-MM-DD (اتركه فارغاً للترخيص الدائم): ").strip()
        if exp_input:
            args.expires = exp_input

    # Generate the cryptographic license token
    token = generate_license_token(
        machine_id=machine_id,
        client_name=args.client,
        plan=args.plan,
        expires_at=args.expires,
    )

    # Double check verification
    valid, msg, payload = verify_license_token(token, target_machine_id=machine_id)
    if not valid:
        print(f"[!] خطأ أثناء التحقق الذاتي من المفتاح: {msg}")
        sys.exit(1)

    print("\n" + "=" * 65)
    print("  ✓ تم إنشاء مفتاح الترخيص بنجاح (License Generated Successfully)")
    print("=" * 65)
    print(f"العميل:       {payload['c']}")
    print(f"معرّف الجهاز: {payload['m']}")
    print(f"النوع:        {payload['p']}")
    print(f"الانتهاء:     {payload['e'] if payload['e'] else 'دائم (Lifetime - No Expiry)'}")
    print("-" * 65)
    print("مفتاح الترخيص (License Key) — قم بنسخه وإرساله للعميل:")
    print("-" * 65)
    print(token)
    print("-" * 65)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(token, encoding="utf-8")
        print(f"[✓] تم حفظ المفتاح مباشرة في الملف: {out_path.resolve()}")


if __name__ == "__main__":
    main()
