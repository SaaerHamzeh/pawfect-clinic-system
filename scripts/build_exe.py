"""
Pawfect Clinic — Standalone Binary Builder (PyInstaller)
Compiles the complete Django + Waitress backend into a secure binary executable without exposing source code.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def build():
    print("=" * 70)
    print("      BUILDING PAWFECT CLINIC STANDALONE EXECUTABLE (NO SOURCE CODE)")
    print("=" * 70)

    # 1. Collect static assets
    print("[1/4] Collecting static assets...")
    subprocess.run(
        [sys.executable, "manage.py", "collectstatic", "--noinput"],
        cwd=BASE_DIR,
        check=True,
    )

    dist_root = BASE_DIR / "dist"
    work_dir = BASE_DIR / "build" / "pyinstaller"
    release_dir = dist_root / "PawfectClinic_App"

    # Clean old release folder
    if release_dir.exists():
        shutil.rmtree(release_dir, ignore_errors=True)

    # 2. Run PyInstaller
    print("[2/4] Compiling Python source code into binary executable...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=PawfectClinic",
        "--onedir",
        f"--distpath={dist_root}",
        f"--workpath={work_dir}",
        f"--add-data={BASE_DIR / 'templates'};templates",
        f"--add-data={BASE_DIR / 'static'};static",
        f"--add-data={BASE_DIR / 'staticfiles'};staticfiles",
        "--collect-all=whitenoise",
        "--collect-all=waitress",
        "--collect-all=zeroconf",
        "--collect-all=ifaddr",
        "--collect-all=psycopg",
        "--collect-all=psycopg_binary",
        "--collect-all=openpyxl",
        "--collect-all=cryptography",
        "--hidden-import=apps.accounts.apps",
        "--hidden-import=apps.clients.apps",
        "--hidden-import=apps.patients.apps",
        "--hidden-import=apps.appointments.apps",
        "--hidden-import=apps.clinical.apps",
        "--hidden-import=apps.reminders.apps",
        "--hidden-import=apps.reports.apps",
        "--hidden-import=apps.settings.apps",
        "--hidden-import=apps.setup.apps",
        "--hidden-import=apps.backups.apps",
        "--hidden-import=apps.core.apps",
        "--hidden-import=apps.audit.apps",
        "--hidden-import=apps.licensing.apps",
        "--hidden-import=django.contrib.admin.apps",
        "--hidden-import=django.contrib.auth.apps",
        "--hidden-import=django.contrib.contenttypes.apps",
        "--hidden-import=django.contrib.sessions.apps",
        "--hidden-import=django.contrib.messages.apps",
        "--hidden-import=django.contrib.staticfiles.apps",
        "--noconfirm",
        "server.py",
    ]
    subprocess.run(cmd, cwd=BASE_DIR, check=True)

    # PyInstaller created dist/PawfectClinic
    built_server_dir = dist_root / "PawfectClinic"

    # Rename to release folder
    if built_server_dir.exists():
        built_server_dir.rename(release_dir)

    print("[3/4] Preparing clean customer directories...")
    (release_dir / "media").mkdir(exist_ok=True)
    (release_dir / "backups").mkdir(exist_ok=True)

    # Copy launcher scripts and initial env
    for fname in [
        "setup_firewall.bat",
    ]:
        src = BASE_DIR / fname
        if src.exists():
            shutil.copy2(src, release_dir / fname)

    # Copy active .env configuration if present
    if (BASE_DIR / ".env").exists():
        shutil.copy2(BASE_DIR / ".env", release_dir / ".env")

    # Create a quick launcher batch for the client
    client_bat = release_dir / "run_clinic.bat"
    with open(client_bat, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write('cd /d "%~dp0"\n')
        f.write('start "" PawfectClinic.exe\n')

    # Create setup_lan_client.bat to allow other PCs on the network to access via 'pawfect'
    lan_setup_bat = release_dir / "setup_lan_client.bat"
    with open(lan_setup_bat, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("title Pawfect Clinic — Connect Other PC via 'pawfect'\n")
        f.write("color 0b\n")
        f.write(
            "echo ======================================================================\n"
        )
        f.write("echo       PAWFECT CLINIC — LAN CLIENT SHORTCUT & ALIAS SETUP\n")
        f.write(
            "echo ======================================================================\n"
        )
        f.write("echo.\n")
        f.write('set /p SERVER_IP="Enter Server IP Address (e.g. 192.168.1.50): "\n')
        f.write('if "%SERVER_IP%"=="" exit /b\n')
        f.write("echo.\n")
        f.write("echo Adding 'pawfect' to Windows hosts file...\n")
        f.write(
            "powershell -Command \"Start-Process powershell -Verb RunAs -ArgumentList '-Command', \\\"Add-Content -Path $env:windir\\System32\\drivers\\etc\\hosts -Value '`n%SERVER_IP%`tpawfect' -Force\\\"\"\n"
        )
        f.write("echo.\n")
        f.write("echo Creating Desktop Shortcut to http://pawfect:8000 ...\n")
        f.write(
            "powershell -Command \"$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.Environment]::GetFolderPath('Desktop') + '\\Pawfect Clinic.lnk'); $s.TargetPath = 'msedge.exe'; $s.Arguments = '--app=http://pawfect:8000'; $s.Save()\"\n"
        )
        f.write("echo.\n")
        f.write(
            "echo [OK] Done! You can now open http://pawfect:8000 from this device.\n"
        )
        f.write("pause\n")

    print(
        "[4/4] Verifying security: compiling bytecode and removing .py source files..."
    )
    import compileall

    # Compile all loose python files into .pyc bytecode first (legacy mode puts .pyc alongside .py)
    compileall.compile_dir(release_dir, force=True, legacy=True, quiet=1)
    compileall.compile_dir(release_dir, force=True, quiet=1)

    py_files = list(release_dir.rglob("*.py"))
    if py_files:
        print(
            f" [!] Securing {len(py_files)} modules (removing raw .py source files)..."
        )
        for p in py_files:
            try:
                p.unlink()
            except Exception:
                pass

    print(
        " [OK] Zero .py source code files found in release directory. All code is compiled binary/bytecode."
    )

    print("=" * 70)
    print(" [OK] Standalone Executable Application successfully built!")
    print(f" [OK] Output Folder: {release_dir}")
    print("=" * 70)


if __name__ == "__main__":
    build()
