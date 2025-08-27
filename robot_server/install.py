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
PYTHON_BIN_PATH = "/usr/bin/python3.11"  # Python 3.11
SYSTEMD_DEST_DIR = INSTALL_DIR / "systemd"


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
        # Check where the app directory is
        if (extracted_dir / "app").exists():
            return extracted_dir / "app"
        elif (extracted_dir / "robot_server").exists():
            return extracted_dir / "robot_server"
        else:
            raise Exception("Neither 'app' nor 'robot_server' directory found in archive.")
    except Exception as e:
        print(f"❌ Failed to extract archive: {e}")
        sys.exit(1)


def create_virtualenv():
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


def create_init_files():
    """Create __init__.py files to make directories Python packages"""
    print("📝 Creating Python package __init__.py files...")
    init_files = [
        INSTALL_DIR / "robot_server" / "__init__.py",
        INSTALL_DIR / "robot_server" / "routers" / "__init__.py", 
        INSTALL_DIR / "robot_server" / "services" / "__init__.py"
    ]
    
    for init_file in init_files:
        init_file.parent.mkdir(parents=True, exist_ok=True)
        init_file.touch()
    
    print("✅ Package structure created")


def install_robot_server():
    print("🤖 LARS Robot Server Installer")

    source_dir = download_and_extract_archive()

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    # Copy robot_server folder
    app_dest = INSTALL_DIR / "robot_server"
    if app_dest.exists():
        shutil.rmtree(app_dest)
    shutil.copytree(source_dir, app_dest)

    # Copy extra files
    for file in ["requirements.txt", "setup_wifi.py"]:
        src_file = source_dir.parent / file if (source_dir.parent / file).exists() else source_dir / file
        if src_file.exists():
            shutil.copy2(src_file, INSTALL_DIR / file)

    # Copy systemd files
    systemd_src = source_dir / "systemd"
    if systemd_src.exists():
        if SYSTEMD_DEST_DIR.exists():
            shutil.rmtree(SYSTEMD_DEST_DIR)
        shutil.copytree(systemd_src, SYSTEMD_DEST_DIR)

    print("✅ Files installed")

    # Create __init__.py files for proper Python package structure
    create_init_files()

    python_bin, pip_bin = create_virtualenv()

    # Install dependencies
    req_file = INSTALL_DIR / "requirements.txt"
    if req_file.exists():
        print("📦 Installing dependencies in virtual environment...")
        run_command([str(pip_bin), "install", "-r", str(req_file)])

    # Setup Wi-Fi
    setup_wifi_script = INSTALL_DIR / "setup_wifi.py"
    if setup_wifi_script.exists():
        print("🌐 Setting up Wi-Fi AP...")
        run_command([str(python_bin), str(setup_wifi_script)], sudo=True, check=False)


if __name__ == "__main__":
    try:
        install_robot_server()
    except KeyboardInterrupt:
        print("\n❌ Installation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)
