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
        # Extract with filter to handle deprecation warning
        with tarfile.open(archive_path, 'r:gz') as tar:
            # Use filter for Python 3.14+ compatibility
            if hasattr(tarfile, 'data_filter'):
                tar.extractall(temp_dir, filter='data')
            else:
                tar.extractall(temp_dir)

        # The archive contains files at root level, not in a robot_server subdirectory
        # So we return temp_dir directly as it contains the extracted files
        extracted_dir = temp_dir

        # Verify that we have the expected files
        app_dir = extracted_dir / "app"
        if not app_dir.exists():
            # If app doesn't exist at root, check if there's a robot_server subdirectory
            robot_server_dir = extracted_dir / "robot_server"
            if robot_server_dir.exists():
                return robot_server_dir
            else:
                raise Exception(
                    f"Neither 'app' directory nor 'robot_server' directory found in archive. Contents: {list(extracted_dir.iterdir())}")

        return extracted_dir

    except Exception as e:
        print(f"❌ Failed to extract archive: {e}")
        # List contents for debugging
        try:
            with tarfile.open(archive_path, 'r:gz') as tar:
                print(f"Archive contents: {tar.getnames()[:10]}")  # Show first 10 files
        except:
            pass
        sys.exit(1)


def install_robot_server():
    """Main installation function."""
    print("🤖 LARS Robot Server Installer")

    # 1️⃣ Скачать и распаковать архив
    source_dir = download_and_extract_archive()

    # 2️⃣ Создать директорию установки
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    # 3️⃣ Копируем приложение
    app_source = source_dir / "app"
    app_dest = INSTALL_DIR / "robot_server"
    if app_dest.exists():
        shutil.rmtree(app_dest)
    shutil.copytree(app_source, app_dest)

    # 4️⃣ Копируем дополнительные файлы
    for file in ["requirements.txt", "setup_wifi.py"]:
        source = source_dir / file
        if source.exists():
            shutil.copy2(source, INSTALL_DIR / file)

    # 5️⃣ Копируем systemd файлы
    systemd_source = source_dir / "systemd"
    systemd_dest = INSTALL_DIR / "systemd"
    if systemd_dest.exists():
        shutil.rmtree(systemd_dest)
    if systemd_source.exists():
        shutil.copytree(systemd_source, systemd_dest)

    print("✅ Files installed")

    # 6️⃣ Устанавливаем зависимости
    req_file = INSTALL_DIR / "requirements.txt"
    if req_file.exists():
        print("📦 Installing dependencies...")
        run_command([sys.executable, "-m", "pip", "install", "-r", str(req_file)])

    # 7️⃣ Настройка Wi-Fi
    setup_wifi_script = INSTALL_DIR / "setup_wifi.py"
    if setup_wifi_script.exists():
        print("🌐 Setting up Wi-Fi AP...")
        run_command([sys.executable, str(setup_wifi_script)], sudo=True, check=False)

    # 8️⃣ Установка и запуск systemd сервиса
    service_file = systemd_dest / "lars-robot-server.service"
    if service_file.exists():
        print("🔧 Installing systemd service...")

        # Заменяем пути в файле сервиса
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

        # Перемещаем в systemd
        if run_command(["cp", str(temp_service), "/etc/systemd/system/lars-robot-server.service"], sudo=True):
            # Перечитываем конфигурацию systemd
            run_command(["systemctl", "daemon-reload"], sudo=True)

            # Включаем автозапуск
            run_command(["systemctl", "enable", "lars-robot-server"], sudo=True)

            # Запускаем сервис
            print("🚀 Starting robot server...")
            if run_command(["systemctl", "start", "lars-robot-server"], sudo=True):
                print("✅ Robot server started!")
                print("📶 Network: LARSrobot / LARSrobot1234")
                print("🌐 Web UI: http://10.42.0.13:8081/docs")

                # Проверка статуса
                print("📊 Checking service status...")
                run_command(["systemctl", "status", "lars-robot-server", "--no-pager"], sudo=True, check=False)
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