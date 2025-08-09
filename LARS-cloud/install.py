#!/usr/bin/env python3

"""
Скрипт установки LARS Cloud

Пользователь запускает:
python3 install.py

Скрипт автоматически:
1. Скачивает tar-архив с проектом
2. Копирует его в текущую директорию (откуда вызван)
3. Распаковывает архив
4. Собирает Docker образы через `docker buildx bake`
"""

import os
import sys
import shutil
import tarfile
import subprocess
import urllib.request
from pathlib import Path

REPO_URL = "https://github.com/LARS-robots/public-install/raw/main/LARS-cloud/lars-cloud.tar.gz"
INSTALL_DIR = "LARS-cloud"

def check_command(command):
    """Проверяет наличие команды в системе"""
    return shutil.which(command) is not None


def check_requirements():
    """Проверяет наличие необходимых утилит"""
    required_commands = {
        'docker': 'Docker не установлен',
        'docker-compose': 'Docker Compose не установлен',
        'python3': 'Python3 не установлен'
    }

    for command, error_msg in required_commands.items():
        if not check_command(command):
            print(f"❌ {error_msg}")
            sys.exit(1)


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


def run_build_script():
    """Запускает скрипт подготовки"""
    try:
        result = subprocess.run([sys.executable, "scripts/build_and_prepare.py"],
                                check=True, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при выполнении скрипта сборки:")
        print(f"Код ошибки: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Файл scripts/build_and_prepare.py не найден")
        sys.exit(1)


def main():
    """Основная функция"""
    print("🚀 Установка LARS Cloud...")

    # Проверяем требования
    check_requirements()

    # Создаем директорию и переходим в неё
    install_path = Path(INSTALL_DIR)
    if install_path.exists():
        print(f"🗑️ Удаляем существующую директорию {INSTALL_DIR}")
        shutil.rmtree(install_path)

    print(f"📁 Создаем директорию {INSTALL_DIR}")
    install_path.mkdir(parents=True, exist_ok=True)

    # Сохраняем текущую директорию и переходим в install_dir
    original_dir = os.getcwd()
    os.chdir(install_path)

    try:
        # Скачиваем архив
        archive_name = "lars-cloud.tar.gz"
        download_file(REPO_URL, archive_name)

        # Распаковываем архив
        extract_archive(archive_name)

        # Удаляем архив
        os.remove(archive_name)
        print(f"🗑️ Удален временный файл {archive_name}")

        # Запускаем скрипт подготовки
        run_build_script()

        print("🎉 Установка LARS Cloud завершена успешно!")

    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)
    finally:
        # Возвращаемся в исходную директорию
        os.chdir(original_dir)


if __name__ == "__main__":
    main()