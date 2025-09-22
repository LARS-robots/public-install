#!/usr/bin/env python3

"""
Скрипт установки LARS Cloud
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
        'docker': 'Docker не установлен. Установите Docker: https://docs.docker.com/get-docker/',
        'docker-compose': 'Docker Compose не установлен',
        'python3': 'Python3 не установлен'
    }

    for command, error_msg in required_commands.items():
        if not check_command(command):
            print(f"❌ {error_msg}")
            sys.exit(1)
    
    print("✅ Все необходимые утилиты установлены")

def download_file(url, filename):
    """Скачивает файл по URL с прогресс-баром"""
    try:
        print(f"📥 Скачиваем {filename}...")
        
        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, (block_num * block_size * 100) // total_size)
                print(f"\r📥 Скачивание: {percent}%", end='', flush=True)
        
        urllib.request.urlretrieve(url, filename, reporthook=progress_hook)
        print(f"\n✅ {filename} скачан")
    except Exception as e:
        print(f"\n❌ Ошибка при скачивании {filename}: {e}")
        sys.exit(1)

def extract_archive(archive_path, extract_to="."):
    """Распаковывает tar.gz архив"""
    try:
        print(f"📦 Распаковываем {archive_path}...")
        with tarfile.open(archive_path, 'r:gz') as tar:
            # ИСПРАВЛЕНИЕ: проверяем содержимое архива
            members = tar.getnames()
            print(f"📋 Найдено файлов в архиве: {len(members)}")
            
            # Проверяем, есть ли корневая директория в архиве
            root_dirs = set()
            for member in members:
                if '/' in member:
                    root_dirs.add(member.split('/')[0])
                else:
                    root_dirs.add('')
            
            tar.extractall(path=extract_to)
            
            # Если в архиве есть корневая директория, возвращаем её путь
            if len(root_dirs) == 1 and list(root_dirs)[0]:
                return Path(extract_to) / list(root_dirs)[0]
            else:
                return Path(extract_to)
                
        print("✅ Архив распакован")
    except Exception as e:
        print(f"❌ Ошибка при распаковке архива: {e}")
        sys.exit(1)

def run_build_script(project_dir):
    """Запускает скрипт подготовки"""
    build_script = project_dir / "scripts" / "build_and_prepare.py"
    
    if not build_script.exists():
        print(f"❌ Файл {build_script} не найден")
        print(f"📁 Содержимое {project_dir}:")
        for item in project_dir.iterdir():
            print(f"  - {item.name}")
        sys.exit(1)
    
    try:
        print(f"🔨 Запускаем сборку из {project_dir}")
        # ИСПРАВЛЕНИЕ: запускаем из правильной директории
        result = subprocess.run([sys.executable, str(build_script)],
                              cwd=project_dir,
                              check=True, text=True)
        print("✅ Сборка завершена успешно")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при выполнении скрипта сборки:")
        print(f"Код ошибки: {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка при сборке: {e}")
        sys.exit(1)

def main():
    """Основная функция"""
    print("🚀 Установка LARS Cloud...")

    # Проверяем требования
    check_requirements()

    # Работаем в текущей директории
    current_dir = Path.cwd()
    install_path = current_dir / INSTALL_DIR
    
    # Удаляем существующую директорию если есть
    if install_path.exists():
        print(f"🗑️ Удаляем существующую директорию {INSTALL_DIR}")
        shutil.rmtree(install_path)

    # Создаем временную директорию для загрузки
    temp_dir = current_dir / "temp_lars_install"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Скачиваем архив во временную директорию
        archive_path = temp_dir / "lars-cloud.tar.gz"
        download_file(REPO_URL, str(archive_path))

        # Распаковываем архив
        print(f"📦 Распаковываем в {current_dir}")
        extracted_path = extract_archive(str(archive_path), str(current_dir))
        
        # ИСПРАВЛЕНИЕ: переименовываем если нужно
        if extracted_path.name != INSTALL_DIR:
            final_path = current_dir / INSTALL_DIR
            if final_path.exists():
                shutil.rmtree(final_path)
            extracted_path.rename(final_path)
            project_dir = final_path
        else:
            project_dir = extracted_path

        print(f"✅ Проект распакован в {project_dir}")

        # Запускаем скрипт подготовки
        run_build_script(project_dir)

        print(f"""
🎉 Установка LARS Cloud завершена успешно!

📁 Проект установлен в: {project_dir}

🚀 Для запуска выполните:
   cd {INSTALL_DIR}
   docker-compose up

🌐 После запуска откройте: http://localhost:7860
        """)

    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)
    finally:
        # Очищаем временные файлы
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print("🗑️ Временные файлы удалены")

if __name__ == "__main__":
    main()