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
SERVICE_FILE = "lars-robot-server.service"

def run_command(cmd, check=True, sudo=False):
    """Run a shell command."""
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd if isinstance(cmd, list) else f"sudo {cmd}"
    
    try:
        result = subprocess.run(cmd, shell=not isinstance(cmd, list), check=check, capture_output=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        return False

def download_and_extract_archive():
    """Download and extract the robot server archive."""
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
        
        # Look for robot_server directory
        robot_server_dir = temp_dir / "robot_server"
        if not robot_server_dir.exists():
            raise Exception("robot_server directory not found in archive")
        
        return robot_server_dir
        
    except Exception as e:
        print(f"❌ Failed to extract archive: {e}")
        sys.exit(1)

def install_robot_server():
    """Main installation function."""
    print("🤖 LARS Robot Server Installer")
    
    source_dir = download_and_extract_archive()
    
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy files
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
    
    # Install dependencies
    req_file = INSTALL_DIR / "requirements.txt"
    if req_file.exists():
        print("📦 Installing dependencies...")
        run_command([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
    
    # Setup Wi-Fi
    setup_wifi_script = INSTALL_DIR / "setup_wifi.py"
    if setup_wifi_script.exists():
        print("🌐 Setting up Wi-Fi AP...")
        run_command([sys.executable, str(setup_wifi_script)], sudo=True, check=False)
    
    # Install and start systemd service
    systemd_dir = INSTALL_DIR / "systemd"
    service_file = systemd_dir / "lars-robot-server.service"
    if service_file.exists():
        print("🔧 Installing systemd service...")
        
        service_content = service_file.read_text()
        service_content = service_content.replace(
            "WorkingDirectory=/home/ubuntu/LARS",
            f"WorkingDirectory={INSTALL_DIR}"
        ).replace(
            "Environment=PYTHONPATH=/home/ubuntu/LARS",
            f"Environment=PYTHONPATH={INSTALL_DIR}"
        ).replace(
            "robot.robot_server.app.main:app",
            "robot_server.app.main:app"
        )
        
        temp_service = Path("/tmp") / "lars-robot-server.service"
        temp_service.write_text(service_content)
        
        if run_command(["cp", str(temp_service), "/etc/systemd/system/lars-robot-server.service"], sudo=True):
            run_command(["systemctl", "daemon-reload"], sudo=True)
            run_command(["systemctl", "enable", "lars-robot-server"], sudo=True)
            
            print("🚀 Starting robot server...")
            if run_command(["systemctl", "start", "lars-robot-server"], sudo=True):
                print("✅ Robot server started!")
                print("📶 Network: LARSrobot / LARSrobot1234")
                print("🌐 Web UI: http://10.42.0.13:8081/docs")
            else:
                print("⚠️  Failed to start service")

if __name__ == "__main__":
    try:
        install_robot_server()
    except KeyboardInterrupt:
        print("\n❌ Installation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)