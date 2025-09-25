#!/usr/bin/env python3

from pathlib import Path
import requests
import tarfile
from io import BytesIO
import venv
import subprocess
import shutil

# config
GITHUB_REPO = "LARS-robots/public-install"
ARCHIVE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/robot_server/robot_server.tar.gz"
INSTALL_DIR = Path.home() / "LARS"
VENV_DIR = INSTALL_DIR / "venv"
SYSTEMD_TARGET = Path("/etc/systemd/system/lars-robot-server.service")

def run_cmd(commands):
    return subprocess.run(commands, check=True)

def download_and_extract(url, extract_to):
    response = requests.get(url)
    response.raise_for_status()
    
    with tarfile.open(fileobj=BytesIO(response.content), mode="r:gz") as tar:
        tar.extractall(path=extract_to)

def reorganize_structure():
    """Move files from app directory to robot_server directory structure"""
    app_dir = INSTALL_DIR / "app"
    robot_server_dir = INSTALL_DIR / "robot_server"
    
    if app_dir.exists():
        print("Moving files from app/ to robot_server/")
        
        # Create robot_server directory if it doesn't exist
        robot_server_dir.mkdir(exist_ok=True)
        
        # Move all contents from app/ to robot_server/
        for item in app_dir.iterdir():
            dest = robot_server_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        
        # Remove the now-empty app directory
        shutil.rmtree(app_dir)
        print("Reorganization complete")
    
    # Also move any other files that should be in robot_server/
    for file_name in ["requirements.txt", "main.py", "config.toml"]:
        src = INSTALL_DIR / file_name
        dest = robot_server_dir / file_name
        if src.exists() and not dest.exists():
            shutil.move(str(src), str(dest))
            print(f"Moved {file_name} to robot_server/")

def create_venv(venv_path):
    venv.create(venv_path, with_pip=True)
    python_exe = venv_path / "bin" / "python"
    
    run_cmd([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"])
    
    run_cmd([str(python_exe), "-m", "pip", "install", "uv"])

    # Look for requirements.txt in robot_server directory
    requirements_path = INSTALL_DIR / "robot_server" / "requirements.txt"
    
    if requirements_path.exists():
        try:
            run_cmd([str(python_exe), "-m", "uv", "pip", "install", "-r", str(requirements_path)])
        except subprocess.CalledProcessError:
            run_cmd([str(python_exe), "-m", "pip", "install", "-r", str(requirements_path)])
    else:
        print(f"Warning: requirements.txt not found at {requirements_path}")

def setup_systemd_service(service_path, target_path):
    if not service_path.exists():
        print(f"Service file {service_path} does not exist.")
        return
    run_cmd(["sudo", "cp", str(service_path), str(target_path)])
    run_cmd(["sudo", "systemctl", "daemon-reload"])
    run_cmd(["sudo", "systemctl", "enable", target_path.name])
    run_cmd(["sudo", "systemctl", "start", target_path.name])


def setup_wifi_script():
    wifi_script = INSTALL_DIR / "setup_wifi.py"
    if wifi_script.exists():
        run_cmd(["python3", str(wifi_script)])
    else:
        print(f"Warning: WiFi setup script not found at {wifi_script}")

def main():
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    
    print("1. Downloading and extracting robot server")
    download_and_extract(ARCHIVE_URL, INSTALL_DIR)
    
    print("2. Reorganizing directory structure")
    reorganize_structure()
    
    print("3. Setting up virtual environment")
    create_venv(VENV_DIR)
    
    print("4. Setting up systemd service")
    service_file = INSTALL_DIR / "systemd" / "lars-robot-server.service"
    if not service_file.exists():
        service_file = INSTALL_DIR / "lars-robot-server.service"
    setup_systemd_service(service_file, SYSTEMD_TARGET)

    print("5. Setting up access points for robot server")
    setup_wifi_script()

    print("Installation complete.")

if __name__ == "__main__":
    main()