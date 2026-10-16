"""
Pawfect Clinic — Offline Production LAN Server (Waitress WSGI)
"""

import os
import sys
import socket
import atexit
from pathlib import Path

# Ensure project root is in python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import subprocess
import threading
import time
import webbrowser

try:
    import django

    django.setup()
    from waitress import serve
    from config.wsgi import application
except ImportError as e:
    print(f"[ERROR] Failed to load server dependencies: {e}")
    sys.exit(1)

try:
    from zeroconf import ServiceInfo, Zeroconf
except ImportError as e:
    print(f"[ERROR] Failed to load mDNS dependency (zeroconf): {e}")
    sys.exit(1)

MDNS_NAME = "pawfect"  # -> resolves on the LAN as pawfect.local


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_client_window(url):
    """Opens the clinic interface in dedicated app window mode (Edge/Chrome) or fallback browser."""
    edge_paths = [
        os.path.expandvars(
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
        ),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for ep in edge_paths:
        if os.path.exists(ep):
            try:
                subprocess.Popen([ep, f"--app={url}"])
                return
            except Exception:
                pass
    try:
        webbrowser.open(url)
    except Exception:
        pass


def open_browser_delayed(url, delay=1.2):
    time.sleep(delay)
    open_client_window(url)


def get_lan_ips():
    """Returns all active local network IPv4 addresses on the clinic LAN."""
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        ips = ["127.0.0.1"]
    return ips


def register_mdns(port, ip):
    """
    Broadcasts 'pawfect.local' on the LAN via mDNS (UDP multicast, port 5353),
    so tablets and PCs alike can resolve the name without editing hosts files.
    Requires UDP 5353 to be open in Windows Firewall (see setup_firewall.bat).
    """
    zc = Zeroconf()
    info = ServiceInfo(
        "_http._tcp.local.",
        f"{MDNS_NAME}._http._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=port,
        server=f"{MDNS_NAME}.local.",
    )
    try:
        zc.register_service(info)
        print(f" [OK] mDNS registered: http://{MDNS_NAME}.local:{port} -> {ip}")
    except Exception as e:
        print(f" [!] mDNS registration failed (name will not resolve): {e}")

    # Ensure the announcement is withdrawn cleanly on shutdown, not left dangling.
    atexit.register(zc.unregister_service, info)
    atexit.register(zc.close)
    return zc


def main():
    port = int(os.environ.get("PORT", 8000))
    local_url = f"http://localhost:{port}"

    # If already running, just bring up the window
    if is_port_in_use(port):
        print(f"[*] Pawfect Clinic is already active at {local_url}.")
        print("[*] Opening client application window...")
        open_client_window(local_url)
        return

    # 1. Automatic database migration check on launch
    try:
        from django.core.management import call_command

        print("[*] Verifying database schema and migrations...")
        call_command("migrate", interactive=False, verbosity=0)
        print(" [OK] Database schema is up to date.")
    except Exception as e:
        print(f" [!] Migration notice: {e}")

    hostname = socket.gethostname()
    lan_ips = get_lan_ips()

    # 2. Register the mDNS alias BEFORE printing the banner, so the [OK]/[!]
    #    line above appears together with the rest of the startup log.
    register_mdns(port, lan_ips[0])

    print("=" * 70)
    print("        PAWFECT VETERINARY CLINIC — APPLICATION SERVER")
    print("=" * 70)
    print(f" [*] Local Application URL:     {local_url}")
    print(
        f" [*] Local Network (By Alias):  http://{MDNS_NAME}.local:{port}   (Android / iPad / Windows)"
    )
    print(
        f" [*] Local Network (By Name):   http://{hostname.lower()}:{port}   (Windows PCs only, NetBIOS)"
    )
    for ip in lan_ips:
        print(f" [*] Local Network (By IP):     http://{ip}:{port}")
    print("=" * 70)
    print(" [*] Launching desktop interface window...")
    print(" [*] Keep this window open while working in the clinic.")
    print("=" * 70)
    print("")

    # Automatically launch desktop client window
    threading.Thread(
        target=open_browser_delayed, args=(local_url,), daemon=True
    ).start()

    serve(
        application,
        host="0.0.0.0",
        port=port,
        threads=8,
        channel_timeout=180,
        max_request_body_size=35
        * 1024
        * 1024,  # 35MB to allow 15MB file uploads + overhead
    )


if __name__ == "__main__":
    main()
