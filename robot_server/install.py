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
SYSTEMD_TARGET_PATH = Path("/etc/systemd/system/lars-robot-server.service")


def run_command(cmd, check=True, sudo=False):
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd if isinstance(cmd, list) else f"sudo {cmd}"
    try:
        result = subprocess.run(
            cmd, shell=not isinstance(cmd, list), check=check,
            capture_output=True, text=True
        )
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        return False


def stop_existing_service():
    """Stop the existing service if it's running"""
    print("🛑 Stopping existing service if running...")
    run_command(["sudo", "systemctl", "stop", "lars-robot-server"], check=False)
    print("✅ Service stopped")


def download_and_extract_archive():
    print("📦 Downloading LARS robot server archive...")
    temp_dir = Path(tempfile.mkdtemp())
    archive_path = temp_dir / "robot_server.tar.gz"
    
    try:
        # Add headers to avoid potential GitHub download issues
        req = urllib.request.Request(ARCHIVE_URL, headers={
            'User-Agent': 'LARS-Robot-Installer/1.0'
        })
        with urllib.request.urlopen(req) as response:
            with open(archive_path, 'wb') as f:
                f.write(response.read())
        print("✅ Archive downloaded")
    except Exception as e:
        print(f"❌ Failed to download archive: {e}")
        print(f"URL: {ARCHIVE_URL}")
        sys.exit(1)

    import tarfile
    try:
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
        
        print(f"📂 Archive extracted to: {temp_dir}")
        
        # List contents to debug
        print("Archive contents:")
        for item in temp_dir.rglob("*"):
            print(f"  {item.relative_to(temp_dir)}")

        # Check for app subdirectory (based on your output)
        app_dir = temp_dir / "app"
        if app_dir.exists() and (app_dir / "main.py").exists():
            print("✅ Found app directory with main.py")
            return temp_dir, app_dir
        elif (temp_dir / "main.py").exists():
            # Files are in the root of the extracted archive
            print("✅ Found main.py in root")
            return temp_dir, temp_dir
        else:
            raise Exception("No valid robot_server structure found in archive")
                
    except Exception as e:
        print(f"❌ Failed to extract archive: {e}")
        sys.exit(1)


def create_virtualenv():
    if not Path(PYTHON_BIN_PATH).exists():
        print(f"❌ Python 3.11 not found at {PYTHON_BIN_PATH}")
        # Try alternative Python paths
        alternatives = ["/usr/bin/python3", "/usr/bin/python"]
        for alt in alternatives:
            if Path(alt).exists():
                print(f"✅ Using alternative Python: {alt}")
                global PYTHON_BIN_PATH
                PYTHON_BIN_PATH = alt
                break
        else:
            sys.exit(1)
    
    # Always recreate virtual environment to ensure clean state
    if VENV_DIR.exists():
        print("🧹 Removing existing virtual environment...")
        shutil.rmtree(VENV_DIR)
    
    print("🐍 Creating Python virtual environment...")
    success = run_command([PYTHON_BIN_PATH, "-m", "venv", str(VENV_DIR)], check=False)
    if not success:
        print("❌ Failed to create virtual environment")
        sys.exit(1)
    
    python_bin = VENV_DIR / "bin" / "python"
    pip_bin = VENV_DIR / "bin" / "pip"
    
    print("📦 Upgrading pip...")
    success = run_command([str(pip_bin), "install", "--upgrade", "pip"], check=False)
    if not success:
        print("⚠️  Pip upgrade failed, continuing anyway...")
    
    return python_bin, pip_bin


def create_init_files():
    print("📝 Creating __init__.py files...")
    init_files = [
        INSTALL_DIR / "robot_server" / "__init__.py",
        INSTALL_DIR / "robot_server" / "routers" / "__init__.py",
        INSTALL_DIR / "robot_server" / "services" / "__init__.py"
    ]
    for init_file in init_files:
        init_file.parent.mkdir(parents=True, exist_ok=True)
        init_file.touch()
    print("✅ Package structure created")


def install_systemd_service():
    service_src = SYSTEMD_DEST_DIR / "lars-robot-server.service"
    if not service_src.exists():
        print(f"❌ Service file not found at: {service_src}")
        print("Available files in systemd directory:")
        if SYSTEMD_DEST_DIR.exists():
            for f in SYSTEMD_DEST_DIR.iterdir():
                print(f"  {f}")
        else:
            print("  No systemd directory found")
        return

    print("🔧 Installing systemd service...")

    service_content = service_src.read_text()
    # Update paths to match the current installation
    service_content = service_content.replace(
        "WorkingDirectory=/home/lars/LARS",
        f"WorkingDirectory={INSTALL_DIR}"
    ).replace(
        "Environment=PYTHONPATH=/home/lars/LARS", 
        f"Environment=PYTHONPATH={INSTALL_DIR}"
    ).replace(
        "/home/lars/LARS/venv/bin/python",
        str(VENV_DIR / "bin" / "python")
    ).replace(
        "LARS.robot_server.main:app",
        "robot_server.main:app"
    ).replace(
        "host 10.42.0.23",
        "host 0.0.0.0"
    )

    temp_service = Path("/tmp") / "lars-robot-server.service"
    temp_service.write_text(service_content)

    print(f"Updated service file content:\n{service_content}")

    # Always overwrite
    if SYSTEMD_TARGET_PATH.exists():
        print("🗑️  Removing existing systemd service...")
        run_command(["sudo", "rm", "-f", str(SYSTEMD_TARGET_PATH)])
    
    run_command(["sudo", "cp", str(temp_service), str(SYSTEMD_TARGET_PATH)])

    # Reload, enable, and restart
    run_command(["sudo", "systemctl", "daemon-reload"])
    run_command(["sudo", "systemctl", "enable", "lars-robot-server.service"])
    run_command(["sudo", "systemctl", "start", "lars-robot-server.service"])

    print("✅ Systemd service installed and started")


def remove_existing_files():
    """Remove existing installation files (except venv which is handled separately)"""
    print("🧹 Removing existing installation files...")
    
    files_to_remove = [
        INSTALL_DIR / "robot_server",
        INSTALL_DIR / "requirements.txt", 
        INSTALL_DIR / "setup_wifi.py",
        INSTALL_DIR / "VERSION",
        SYSTEMD_DEST_DIR
    ]
    
    for item in files_to_remove:
        if item.exists():
            if item.is_dir():
                print(f"  Removing directory: {item}")
                shutil.rmtree(item)
            else:
                print(f"  Removing file: {item}")
                item.unlink()
    
    print("✅ Existing files removed")


def install_robot_server():
    print("🤖 Installing LARS Robot Server...")
    print("🔄 This installation will overwrite existing files")
    
    # Stop service before making changes
    stop_existing_service()
    
    # Remove existing files
    remove_existing_files()
    
    temp_dir, app_dir = download_and_extract_archive()

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    # Create robot_server directory and copy files from app_dir
    app_dest = INSTALL_DIR / "robot_server"
    app_dest.mkdir(parents=True, exist_ok=True)
    
    print("📁 Installing application files...")
    # Copy application files to robot_server directory
    app_files = ["main.py", "deps.py", "state.py"]
    for file in app_files:
        src_file = app_dir / file
        if src_file.exists():
            print(f"  Copying: {file}")
            shutil.copy2(src_file, app_dest)
        else:
            print(f"  ⚠️  Missing: {file}")
    
    # Copy directories (force overwrite)
    app_dirs = ["routers", "services", "static"]
    for dir_name in app_dirs:
        src_dir = app_dir / dir_name
        if src_dir.exists():
            dest_dir = app_dest / dir_name
            print(f"  Copying directory: {dir_name}")
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
        else:
            print(f"  ⚠️  Missing directory: {dir_name}")

    # Copy root level files from temp_dir (not app_dir)
    root_files = ["requirements.txt", "setup_wifi.py", "VERSION"]
    for file in root_files:
        src_file = temp_dir / file
        if src_file.exists():
            dest_file = INSTALL_DIR / file
            print(f"  Copying: {file}")
            if dest_file.exists():
                dest_file.unlink()
            shutil.copy2(src_file, dest_file)
        else:
            print(f"  ⚠️  Missing: {file}")

    # Copy systemd directory from temp_dir (not app_dir)
    systemd_src = temp_dir / "systemd"
    if systemd_src.exists():
        print(f"  Copying systemd configuration...")
        if SYSTEMD_DEST_DIR.exists():
            shutil.rmtree(SYSTEMD_DEST_DIR)
        shutil.copytree(systemd_src, SYSTEMD_DEST_DIR)
        print(f"  ✅ Systemd files copied")
    else:
        print(f"  ❌ No systemd directory found")

    print("✅ Files installed")

    create_init_files()

    python_bin, pip_bin = create_virtualenv()
    req_file = INSTALL_DIR / "requirements.txt"
    if req_file.exists():
        print("📦 Installing dependencies in virtual environment...")
        success = run_command([str(pip_bin), "install", "-r", str(req_file)], check=False)
        if not success:
            print("⚠️  Some dependencies may have failed to install")

    setup_wifi_script = INSTALL_DIR / "setup_wifi.py"
    if setup_wifi_script.exists():
        print("🌐 Setting up Wi-Fi AP...")
        run_command([str(python_bin), str(setup_wifi_script)], sudo=True, check=False)

    install_systemd_service()

    print(f"\n🎉 Installation completed!")
    print(f"📁 Robot server installed to: {INSTALL_DIR}")
    print(f"🔧 Service status:")
    run_command(["sudo", "systemctl", "status", "lars-robot-server", "--no-pager"], check=False)


if __name__ == "__main__":
    try:
        install_robot_server()
    except KeyboardInterrupt:
        print("\n❌ Installation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)
