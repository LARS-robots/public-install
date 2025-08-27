#!/usr/bin/env python3
"""
LARS Robot Server Installer
Downloads and installs LARS robot server from GitHub archive.
"""

import os
import sys
import subprocess
import shutil
import tempfile
import urllib.request
from pathlib import Path

# Configuration
GITHUB_REPO = "LARS-robots/public-install"
ARCHIVE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/robot_server/robot_server.tar.gz"
INSTALL_DIR = Path.home() / "LARS"
VENV_DIR = INSTALL_DIR / "venv"
SERVICE_FILE = "lars-robot-server.service"
PYTHON_BIN_PATH = "/usr/bin/python3.11"  # Используем конкретный Python 3.11

def run_command(cmd, check=True, sudo=False):
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd if isinstance(cmd, list) else f"sudo {cmd}"
    try:
        result = subprocess.run(cmd, shell=not isinstance(cmd, list), check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False

def download_and_extract_archive():
    print("📦 Downloading LARS robot server archive...")
    temp_dir = Path(tempfile.mkdtemp())
    archive_path = temp_dir / "robot_server.tar.gz"
    try:
        urllib.request.urlretrieve(ARCHIVE_URL, archive_path)
        print("✅ Archive downloaded")
    except Exception as e:
        print(f"❌ Failed to download archive: {e}")
        sys.exit(1)
    import tarfile
    try:
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
        extracted_dir = temp_dir
        app_dir = extracted_dir / "app"
        if not app_dir.exists():
            robot_server_dir = extracted_dir / "robot_server"
            if robot_server_dir.exists():
                return robot_server_dir
            else:
                raise Exception(f"Neither 'app' nor 'robot_server' directory found in archive.")
        return extracted_dir
    except Exception as e:
        print(f"❌ Failed to extract archive: {e}")
        sys.exit(1)

def create_virtualenv():
    """Create a Python 3.11 virtual environment and return python/pip paths."""
    if not Path(PYTHON_BIN_PATH).exists():
        print(f"❌ Python 3.11 not found at {PYTHON_BIN_PATH}")
        sys.exit(1)
    if not VENV_DIR.exists():
        print("🐍 Creating Python 3.11 virtual environment...")
        run_command([PYTHON_BIN_PATH, "-m", "venv", str(VENV_DIR)])
    python_bin = VENV_DIR / "bin" / "python"
    pip_bin = VENV_DIR / "bin" / "pip"
    run_command([str(pip_bin), "install", "--upgrade", "pip"])
    return python_bin, pip_bin

def install_robot_server():
    print("🤖 LARS Robot Server Installer")
    source_dir = download_and_extract_archive()
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    app_source = source_dir / "app"
    app_dest = INSTALL_DIR / "robot_server"
    if app_dest.exists():
        shutil.rmtree(app_dest)
    shutil.copytree(app_source, app_dest)
    for file in ["requirements.txt", "setup_wifi.py"]:
        source = source_dir / file
        if source.exists():
            shutil.copy2(source, INSTALL_DIR / file)
    systemd_source = source_dir / "systemd"
    systemd_dest = INSTALL_DIR / "systemd"
    if systemd_dest.exists():
        shutil.rmtree(systemd_dest)
    if systemd_source.exists():
        shutil.copytree(systemd_source, systemd_dest)
    print("✅ Files installed")

    python_bin, pip_bin = create_virtualenv()
    req_file = INSTALL_DIR / "requirements.txt"
    if req_file.exists():
        print("📦 Installing dependencies in virtual environment...")
        run_command([str(pip_bin), "install", "-r", str(req_file)])

    setup_wifi_script = INSTALL_DIR / "setup_wifi.py"
    if setup_wifi_script.exists():
        print("🌐 Setting up Wi-Fi AP...")
        run_command([str(python_bin), str(setup_wifi_script)], sudo=True, check=False)

    service_file = systemd_dest / "lars-robot-server.service"
    if service_file.exists():
        print("🔧 Installing systemd service...")
        service_content = service_file.read_text()
        service_content = service_content.replace(
            "WorkingDirectory=/home/ubuntu/LARS",
            f"WorkingDirectory={INSTALL_DIR}"
        ).replace(
            "Environment=PYTHONPATH=/home/ubuntu/LARS",
            ""
        ).replace(
            "robot.robot_server.app.main:app",
            "robot_server.app.main:app"
        )
        service_content = service_content.replace(
            "/usr/bin/python3",
            str(python_bin)
        )
        temp_service = Path("/tmp") / "lars-robot-server.service"
        temp_service.write_text(service_content)
        if run_command(["cp", str(temp_service), "/etc/systemd/system/lars-robot-server.service"], sudo=True):
            run_command(["systemctl", "daemon-reload"], sudo=True)
            run_command(["systemctl", "enable", "lars-robot-server"], sudo=True)
            print("🚀 Starting robot server...")
            if run_command(["systemctl", "start", "lars-robot-server"], sudo=True):
                print("✅ Robot server started!")
                run_command(["systemctl", "status", "lars-robot-server", "--no-pager"], sudo=True, check=False)
            else:
                print("⚠️ Failed to start service")

if __name__ == "__main__":
    try:
        install_robot_server()
    except KeyboardInterrupt:
        print("\n❌ Installation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)
