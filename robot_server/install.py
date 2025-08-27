#!/usr/bin/env python3
"""
LARS Robot Server Installer (fixed, robust)
- creates a python venv (prefers /usr/bin/python3.11, falls back to /usr/bin/python3)
- installs requirements into the venv
- writes/overwrites /etc/systemd/system/lars-robot-server.service and enables+starts it
"""

import os
import sys
import subprocess
import shutil
import tempfile
import urllib.request
from pathlib import Path

# Config
GITHUB_REPO = "LARS-robots/public-install"
ARCHIVE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/robot_server/robot_server.tar.gz"
INSTALL_DIR = Path.home() / "LARS"
VENV_DIR = INSTALL_DIR / "venv"
SYSTEMD_TARGET = Path("/etc/systemd/system/lars-robot-server.service")


def run_cmd(cmd, check=True, sudo=False):
    """Run command and print stdout/stderr. Return (rc, stdout, stderr)."""
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + (cmd if isinstance(cmd, list) else [cmd])
    try:
        cp = subprocess.run(cmd, shell=not isinstance(cmd, list),
                            check=check, capture_output=True, text=True)
        out = cp.stdout.strip()
        err = cp.stderr.strip()
        if out:
            print(out)
        if err:
            print(err)
        return cp.returncode, out, err
    except subprocess.CalledProcessError as e:
        print("❌ Command failed:", e)
        return e.returncode, getattr(e, 'stdout', ''), getattr(e, 'stderr', '')


def download_and_extract():
    print("📦 Downloading archive...")
    tmp = Path(tempfile.mkdtemp())
    archive = tmp / "robot_server.tar.gz"
    try:
        req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "LARS-installer"})
        with urllib.request.urlopen(req) as r, open(archive, "wb") as f:
            f.write(r.read())
    except Exception as e:
        print("❌ Download failed:", e)
        sys.exit(1)

    import tarfile
    try:
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(tmp)
    except Exception as e:
        print("❌ Extract failed:", e)
        sys.exit(1)

    # Determine app dir (archive might contain `app/` or `robot_server/`)
    if (tmp / "app").exists():
        return tmp, tmp / "app"
    if (tmp / "robot_server").exists():
        return tmp, tmp / "robot_server"
    # fallback: root
    return tmp, tmp


def find_python():
    candidates = ["/usr/bin/python3.11", "/usr/bin/python3", shutil.which("python3") or "/usr/bin/python3"]
    for p in candidates:
        if Path(p).exists():
            print(f"✅ Using Python: {p}")
            return p
    print("❌ No suitable Python found. Install python3 or python3.11.")
    sys.exit(1)


def make_venv(python_bin):
    # Remove existing venv for clean state
    if VENV_DIR.exists():
        print("🧹 Removing existing venv...")
        shutil.rmtree(VENV_DIR)
    print("🐍 Creating venv...")
    rc, out, err = run_cmd([python_bin, "-m", "venv", str(VENV_DIR)], check=False)
    if rc != 0:
        print("❌ venv creation failed. Ensure python3-venv is installed.")
        sys.exit(1)
    python_in_venv = VENV_DIR / "bin" / "python"
    pip_in_venv = VENV_DIR / "bin" / "pip"
    # upgrade pip (best-effort)
    print("📦 Upgrading pip inside venv (best-effort)...")
    rc, out, err = run_cmd([str(pip_in_venv), "install", "--upgrade", "pip"], check=False)
    if rc != 0:
        print("⚠️ pip upgrade failed (continuing). Check pip stderr above.")
    return str(python_in_venv), str(pip_in_venv)


def ensure_init_files():
    """Create __init__.py to make imports deterministic (helps old-style imports)."""
    files = [
        INSTALL_DIR / "robot_server" / "__init__.py",
        INSTALL_DIR / "robot_server" / "routers" / "__init__.py",
        INSTALL_DIR / "robot_server" / "services" / "__init__.py",
    ]
    for f in files:
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.touch()


def write_systemd_unit(python_bin):
    """Write a deterministic systemd unit that uses the venv python."""
    unit_text = f"""[Unit]
Description=LARS Robot Server
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
User={os.getlogin()}
Group={os.getlogin()}
WorkingDirectory={INSTALL_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart={python_bin} -m uvicorn robot_server.main:app --host 0.0.0.0 --port 8081
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
"""
    # write temp and copy with sudo, always overwrite
    tmp = Path("/tmp/lars-robot-server.service")
    tmp.write_text(unit_text)
    print("🔧 Installing systemd unit to /etc/systemd/system (overwriting)...")
    rc, _, _ = run_cmd(["sudo", "cp", str(tmp), str(SYSTEMD_TARGET)], check=False)
    if rc != 0:
        print("❌ Failed to copy systemd unit. You may rerun with sudo.")
        sys.exit(1)
    run_cmd(["sudo", "systemctl", "daemon-reload"])
    run_cmd(["sudo", "systemctl", "enable", "lars-robot-server.service"])
    run_cmd(["sudo", "systemctl", "restart", "lars-robot-server.service"])
    run_cmd(["sudo", "systemctl", "status", "lars-robot-server", "--no-pager"], check=False)


def install():
    print("🤖 Installing LARS (this will overwrite existing install)...")
    # stop existing service
    run_cmd(["sudo", "systemctl", "stop", "lars-robot-server"], check=False)
    # clean old files
    print("🧹 Removing old installation (if present)...")
    for p in ["robot_server", "requirements.txt", "setup_wifi.py", "systemd", "VERSION"]:
        tgt = INSTALL_DIR / p
        if tgt.exists():
            if tgt.is_dir():
                shutil.rmtree(tgt)
                print(f"  removed dir {tgt}")
            else:
                tgt.unlink()
                print(f"  removed file {tgt}")

    temp_dir, app_src = download_and_extract()
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    app_dest = INSTALL_DIR / "robot_server"
    if app_dest.exists():
        shutil.rmtree(app_dest)
    print("📁 Copying application files...")
    shutil.copytree(app_src, app_dest)
    # copy top-level files (requirements, setup_wifi, VERSION) if present in temp_dir
    for root_file in ["requirements.txt", "setup_wifi.py", "VERSION"]:
        src = temp_dir / root_file
        if src.exists():
            dest = INSTALL_DIR / root_file
            if dest.exists():
                dest.unlink()
            shutil.copy2(src, dest)
            print(f"  copied {root_file}")

    # copy systemd dir if present
    src_systemd = temp_dir / "systemd"
    if src_systemd.exists():
        dest_systemd = INSTALL_DIR / "systemd"
        if dest_systemd.exists():
            shutil.rmtree(dest_systemd)
        shutil.copytree(src_systemd, dest_systemd)
        print("  copied systemd directory from archive")

    # create __init__ files
    ensure_init_files()

    python_choice = find_python()
    python_bin, pip_bin = make_venv(python_choice)

    # install dependencies if requirements.txt present
    req = INSTALL_DIR / "requirements.txt"
    if req.exists():
        print("📦 Installing requirements into venv (this step may need build deps: build-essential, python3-dev, libffi-dev, ffmpeg etc)...")
        rc, out, err = run_cmd([pip_bin, "install", "-r", str(req)], check=False)
        if rc != 0:
            print("⚠️ Some dependencies failed to install. Check stderr above and install system packages (see README).")

    # run setup_wifi (best-effort, sudo)
    setup_py = INSTALL_DIR / "setup_wifi.py"
    if setup_py.exists():
        print("🌐 Running setup_wifi.py (best-effort, may require sudo)...")
        run_cmd([python_bin, str(setup_py)], sudo=True, check=False)

    # install systemd unit (use the venv python to guarantee correct ExecStart)
    write_systemd_unit(python_bin)

    print("🎉 Installation finished. If service failed to start, run:")
    print("  sudo journalctl -u lars-robot-server -b -n 200 --no-pager")
    print("  sudo systemctl status lars-robot-server --no-pager")


if __name__ == "__main__":
    install()
