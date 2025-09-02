import os
import sys
import shutil
import tarfile
import subprocess
import urllib.request
from pathlib import Path

REPO_URL = "https://github.com/LARS-robots/public-install/raw/main/fleet_server/fleet_server.tar.gz"
INSTALL_DIR = "fleet_server"


def download_file(url, filename):
    """Скачивает файл по URL"""
    try:
        print(f"📥 Скачиваем {filename}...")
        urllib.request.urlretrieve(url, filename)
        print(f"✅ {filename} скачан")
    except Exception as e:
        print(f"❌ Ошибка при скачивании {filename}: {e}")
        sys.exit(1)

def extract_archive(archive_path, extract_to="."):
    """Распаковывает tar.gz архив"""
    try:
        print(f"📦 Распаковываем {archive_path}...")
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=extract_to)
        print("✅ Архив распакован")
    except Exception as e:
        print(f"❌ Ошибка при распаковке архива: {e}")
        sys.exit(1)

def main():
    # Скачиваем архив
    archive_name = "fleet_server.tar.gz"
    download_file(REPO_URL, archive_name)

    # Распаковываем
    extract_archive(archive_name)
    os.remove(archive_name)
    print(f"✅ Проект установлен в папку {INSTALL_DIR}")

if __name__ == "__main__":
    main()