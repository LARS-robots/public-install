#!/usr/bin/env python3
"""
LARS Robot Server Installer — use systemd unit from repo unchanged
This installer:
 - downloads robot_server archive,
 - copies application files into ~/LARS/robot_server,
 - creates a Python venv (prefer python3.11),
 - installs requirements in the venv,
 - runs setup_wifi.py (best-effort),
 - copies systemd/lars-robot-server.service from repo into /etc/systemd/system,
   replacing "LARS.robot_server" with "robot_server" if present,
 - enables & starts the service.
"""
from pathlib import Path
import urllib.request
import tarfile
import tempfile
import shutil
import subprocess
import sys
import os
import re

# -------- CONFIG --------
GITHUB_REPO = "LARS-robots/public-install"
ARCHIVE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/robot_server/robot_server.tar.gz"
INSTALL_DIR = Path.home() / "LARS"
VENV_DIR = INSTALL_DIR / "venv"
SYSTEMD_TARGET = Path("/etc/systemd/system/lars-robot-server.service")


# -------- helpers --------
def run_cmd(cmd, check=True, sudo=False):
    if sudo and os.geteuid() != 0:
        if isinstance(cmd, list):
            cmd = ["sudo"] + cmd
        else:
            cmd = "sudo " + cmd
    print("▶", cmd if isinstance(cmd, str) else " ".join(cmd))
    return subprocess.run(cmd, shell=not isinstance(cmd, list), check=check)


def download_and_extract():
    tmp = Path(tempfile.mkdtemp())
    archive = tmp / "robot_server.tar.gz"
    print("Downloading", ARCHIVE_URL)
    req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "LARS-installer"})
    with urllib.request.urlopen(req) as r, open(archive, "wb") as f:
        f.write(r.read())

    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(tmp)

    if (tmp / "app").exists():
        app_dir = tmp / "app"
    elif (tmp / "robot_server").exists():
        app_dir = tmp / "robot_server"
    else:
        app_dir = tmp

    print("Archive extracted to:", tmp)
    return tmp, app_dir


def find_python_prefer_311():
    candidates = ["/usr/bin/python3.11", "/usr/bin/python3", shutil.which("python3") or "/usr/bin/python3"]
    for c in candidates:
        if c and Path(c).exists():
            print("Using python:", c)
            return str(c)
    print("❌ No Python found; please install python3.")
    sys.exit(1)


def create_venv(python_bin):
    if VENV_DIR.exists():
        print("Removing existing venv:", VENV_DIR)
        shutil.rmtree(VENV_DIR)
    print("Creating venv with", python_bin)
    subprocess.run([python_bin, "-m", "venv", str(VENV_DIR)], check=True)
    return str(VENV_DIR / "bin" / "python"), str(VENV_DIR / "bin" / "pip")


def copy_app_files(app_src):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    dest = INSTALL_DIR / "robot_server"
    if dest.exists():
        shutil.rmtree(dest)
    print("Copying app to", dest)
    shutil.copytree(app_src, dest)

    for name in ["requirements.txt", "setup_wifi.py", "VERSION"]:
        src = app_src.parent / name if (app_src.parent / name).exists() else app_src / name
        if src.exists():
            shutil.copy2(src, INSTALL_DIR / name)

    src_systemd = app_src.parent / "systemd"
    if src_systemd.exists():
        dest_systemd = INSTALL_DIR / "systemd"
        if dest_systemd.exists():
            shutil.rmtree(dest_systemd)
        shutil.copytree(src_systemd, dest_systemd)


def install_requirements(pip_bin):
    req = INSTALL_DIR / "requirements.txt"
    if req.exists():
        subprocess.run([pip_bin, "install", "-r", str(req)], check=False)


def run_setup_wifi(python_bin):
    setup_script = INSTALL_DIR / "setup_wifi.py"
    if setup_script.exists():
        subprocess.run(["sudo", python_bin, str(setup_script)], check=False)


def install_systemd_unit():
    repo_service = INSTALL_DIR / "systemd" / "lars-robot-server.service"
    if not repo_service.exists():
        print("❌ No service file found at", repo_service)
        return False

    txt = repo_service.read_text()
    txt = txt.replace("LARS.robot_server", "robot_server")  # normalize import path if needed

    tmp = Path("/tmp/lars-robot-server.service")
    tmp.write_text(txt)

    run_cmd(["sudo", "cp", str(tmp), str(SYSTEMD_TARGET)], check=True)
    run_cmd(["sudo", "systemctl", "daemon-reload"])
    run_cmd(["sudo", "systemctl", "enable", "lars-robot-server.service"])
    run_cmd(["sudo", "systemctl", "restart", "lars-robot-server.service"], check=False)
    return True


def main():
    print("=== LARS Robot Server installer ===")
    run_cmd(["sudo", "systemctl", "stop", "lars-robot-server"], check=False)

    for item in ["robot_server", "requirements.txt", "setup_wifi.py", "systemd", "VERSION"]:
        p = INSTALL_DIR / item
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    tmp_dir, app_src = download_and_extract()
    copy_app_files(app_src)

    python_choice = find_python_prefer_311()
    venv_python, venv_pip = create_venv(python_choice)

    install_requirements(venv_pip)
    run_setup_wifi(venv_python)

    if not install_systemd_unit():
        print("⚠️ Service unit not installed.")

    print("\nDone. Check service with:")
    print("  sudo systemctl status lars-robot-server --no-pager")
    print("  sudo journalctl -u lars-robot-server -b --no-pager")


if __name__ == "__main__":
    main()
