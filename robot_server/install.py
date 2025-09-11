#!/usr/bin/env python3
"""
LARS Robot Server Installer (версии без pigpio/pigpiod)
"""

from pathlib import Path
import urllib.request
import tarfile
import tempfile
import shutil
import subprocess
import sys
import os
import traceback

# -------- CONFIG --------
GITHUB_REPO = "LARS-robots/public-install"
ARCHIVE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/robot_server/robot_server.tar.gz"
INSTALL_DIR = Path.home() / "LARS"
VENV_DIR = INSTALL_DIR / "venv"
SYSTEMD_TARGET = Path("/etc/systemd/system/lars-robot-server.service")

# Проблемные/встроенные пакеты, которые не нужно устанавливать
SKIP_PACKAGES = {
    'contextlib',      # встроенный модуль Python
    'typing',          # встроенный в Python 3.5+
    'dataclasses',     # встроенный в Python 3.7+
    'pathlib',         # встроенный в Python 3.4+
    'asyncio',         # встроенный в Python 3.4+
    'json',            # встроенный модуль
    'datetime',        # встроенный модуль
    'logging',         # встроенный модуль
    'os',              # встроенный модуль
    'sys',             # встроенный модуль
}

# Проблемные пакеты, которые требуют особого внимания
PROBLEMATIC_PACKAGES = {
    'aiozeroconf': 'zeroconf>=0.131.0 aiozeroconf>=0.1.8',
}

# -------- helpers --------
def run_cmd(cmd, check=True, sudo=False):
    if sudo and os.geteuid() != 0:
        if isinstance(cmd, list):
            cmd = ["sudo"] + cmd
        else:
            cmd = "sudo " + cmd
    print("▶", cmd if isinstance(cmd, str) else " ".join(cmd))
    return subprocess.run(cmd, shell=not isinstance(cmd, list), check=check)

def is_text_file(file_path):
    """Проверяет, является ли файл текстовым"""
    try:
        with open(file_path, 'rb') as f:
            # Читаем первые 1024 байта
            chunk = f.read(1024)
            if not chunk:
                return True  # пустой файл считаем текстовым
            
            # Проверяем на наличие нулевых байтов (признак бинарного файла)
            if b'\x00' in chunk:
                return False
            
            # Пытаемся декодировать как UTF-8
            chunk.decode('utf-8')
            return True
    except (UnicodeDecodeError, IOError):
        return False

def safe_read_text(file_path, encoding='utf-8'):
    """Безопасное чтение текстового файла с проверкой"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not is_text_file(file_path):
        raise ValueError(f"File is not a text file: {file_path}")
    
    try:
        return file_path.read_text(encoding=encoding)
    except UnicodeDecodeError as e:
        print(f"⚠️ UTF-8 decode error in {file_path}, trying latin-1...")
        try:
            return file_path.read_text(encoding='latin-1')
        except Exception:
            raise e

def download_and_extract():
    tmp = Path(tempfile.mkdtemp())
    archive = tmp / "robot_server.tar.gz"
    print("Downloading", ARCHIVE_URL)
    
    try:
        req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "LARS-installer"})
        with urllib.request.urlopen(req) as r:
            # Проверяем Content-Type
            content_type = r.headers.get('Content-Type', '')
            print(f"Content-Type: {content_type}")
            
            with open(archive, "wb") as f:
                f.write(r.read())
                
        print(f"Downloaded {archive.stat().st_size} bytes")
    except Exception as e:
        print(f"❌ Failed to download: {e}")
        sys.exit(1)

    try:
        # Проверяем, что файл действительно является архивом
        if not tarfile.is_tarfile(archive):
            print(f"❌ Downloaded file is not a valid tar archive")
            print(f"File size: {archive.stat().st_size} bytes")
            # Показываем первые байты для диагностики
            with open(archive, 'rb') as f:
                first_bytes = f.read(16)
                print(f"First bytes: {first_bytes.hex()}")
            sys.exit(1)
            
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp)
    except Exception as e:
        print(f"❌ Failed to extract archive: {e}")
        print(f"Archive size: {archive.stat().st_size} bytes")
        sys.exit(1)

    # Поиск директории с приложением
    possible_dirs = [tmp / "app", tmp / "robot_server", tmp]
    app_dir = None
    
    for dir_path in possible_dirs:
        if dir_path.exists() and dir_path.is_dir():
            # Проверяем наличие признаков приложения
            if any((dir_path / f).exists() for f in ["main.py", "app", "__init__.py"]):
                app_dir = dir_path
                break
    
    if app_dir is None:
        # Используем первую найденную директорию
        subdirs = [d for d in tmp.iterdir() if d.is_dir()]
        if subdirs:
            app_dir = subdirs[0]
        else:
            app_dir = tmp

    print(f"Archive extracted to: {tmp}")
    print(f"App directory: {app_dir}")
    return tmp, app_dir

def copy_app_files(app_src):
    """Копирует файлы приложения в целевую директорию LARS/robot_server/"""
    
    # Целевая директория должна быть LARS/robot_server, а не просто LARS
    target_dir = INSTALL_DIR / "robot_server"
    
    print(f"Copying app files from {app_src} to {target_dir}")
    
    # Создаем целевую директорию
    INSTALL_DIR.mkdir(exist_ok=True)
    target_dir.mkdir(exist_ok=True)
    
    # Копируем содержимое приложения в robot_server/
    for item in app_src.iterdir():
        dest = target_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
            print(f"  📁 robot_server/{item.name}/")
        else:
            shutil.copy2(item, dest)
            print(f"  📄 robot_server/{item.name}")
    
    # Также копируем файлы верхнего уровня (если есть) в LARS/
    for top_level_file in ["requirements.txt", "setup_wifi.py", "VERSION"]:
        src_file = app_src / top_level_file
        if src_file.exists():
            dest_file = INSTALL_DIR / top_level_file
            shutil.copy2(src_file, dest_file)
            print(f"  📄 {top_level_file}")

def create_venv(python_bin):
    """Создает виртуальное окружение"""
    print(f"Creating virtual environment with {python_bin}")
    
    # Удаляем старое окружение если есть
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    
    # Создаем новое
    result = subprocess.run([python_bin, "-m", "venv", str(VENV_DIR)], check=False)
    if result.returncode != 0:
        print("❌ Failed to create virtual environment")
        sys.exit(1)
    
    venv_python = VENV_DIR / "bin" / "python"
    venv_pip = VENV_DIR / "bin" / "pip"
    
    if not venv_python.exists() or not venv_pip.exists():
        print("❌ Virtual environment creation failed")
        sys.exit(1)
    
    # Обновляем pip в venv
    subprocess.run([str(venv_pip), "install", "--upgrade", "pip"], check=False)
    
    print(f"✅ Virtual environment created at {VENV_DIR}")
    return str(venv_python), str(venv_pip)

def find_python_prefer_stable():
    """Находит подходящую версию Python, предпочтительно 3.11 для стабильности"""
    candidates = [
        "/usr/bin/python3.11",  # предпочтительная стабильная версия
        "/usr/bin/python3.10",  # альтернативная стабильная
        "/usr/bin/python3.12",  # новая, но может иметь проблемы совместимости
        "/usr/bin/python3.9",   # старая, но надежная
        "/usr/bin/python3",
        shutil.which("python3") or "/usr/bin/python3",
    ]
    
    fallback_python = None
    
    for c in candidates:
        if c and Path(c).exists():
            try:
                result = subprocess.run([c, "--version"], capture_output=True, text=True)
                version_str = result.stdout.strip()
                version_parts = version_str.split()[1].split('.')
                major, minor = int(version_parts[0]), int(version_parts[1])
                
                # Предпочитаем Python 3.10-3.11 для максимальной совместимости
                if major == 3 and 10 <= minor <= 11:
                    print(f"✅ Found preferred Python: {c} ({version_str})")
                    return str(c)
                elif major == 3 and minor >= 9:
                    print(f"Found acceptable Python: {c} ({version_str})")
                    # Продолжаем поиск, но запоминаем как запасной вариант
                    if fallback_python is None:
                        fallback_python = str(c)
            except Exception:
                continue
    
    # Если не нашли идеальную версию, используем запасную
    if fallback_python is not None:
        print(f"⚠️ Using fallback Python: {fallback_python}")
        return fallback_python
    
    print("❌ No suitable Python found; please install python3.11 or python3.10.")
    print("Run: sudo apt update && sudo apt install python3.11 python3.11-venv python3.11-dev")
    sys.exit(1)

def install_system_dependencies():
    """Устанавливает системные зависимости"""
    print("Installing system dependencies...")
    run_cmd(["sudo", "apt", "update"], check=True)
    
    # Системные пакеты для Python и мультимедиа
    system_packages = [
        "python3-pip", "python3-dev", "python3-setuptools", "python3-venv",
        "python3-gpiozero", "python3-lgpio", "gpiod",
        "build-essential", "pkg-config",
        "libavformat-dev", "libavcodec-dev", "libavdevice-dev", "libavutil-dev",
        "libavfilter-dev", "libswscale-dev", "libswresample-dev",
        "libopus-dev", "libvpx-dev", "libsrtp2-dev",
        "cmake", "libssl-dev", "libffi-dev",
        # Зависимости для zeroconf
        "libavahi-compat-libdnssd-dev", "avahi-utils",
    ]
    
    for package in system_packages:
        print(f"Installing {package}...")
        result = run_cmd(["sudo", "apt", "install", "-y", package], check=False)
        if result.returncode != 0:
            print(f"⚠️ Failed to install {package}, continuing...")

def clean_requirements_txt(req_file):
    """Очищает requirements.txt от проблемных пакетов"""
    
    # Ищем requirements.txt в правильных локациях
    possible_req_files = [
        INSTALL_DIR / "requirements.txt",
        INSTALL_DIR / "robot_server" / "requirements.txt",
    ]
    
    actual_req_file = None
    for req_path in possible_req_files:
        if req_path.exists():
            actual_req_file = req_path
            break
    
    if actual_req_file is None:
        print(f"⚠️ Requirements file not found in expected locations")
        return
    
    if not is_text_file(actual_req_file):
        print(f"⚠️ Requirements file is not a text file: {actual_req_file}")
        return
    
    print(f"Cleaning requirements.txt at {actual_req_file}")
    lines = []
    skipped = []
    replaced = []
    
    try:
        content = safe_read_text(actual_req_file)
        for line in content.splitlines():
            original_line = line.strip()
            if not original_line or original_line.startswith('#'):
                lines.append(original_line)
                continue
            
            # Извлекаем имя пакета
            package_name = original_line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].strip()
            
            if package_name.lower() in SKIP_PACKAGES:
                skipped.append(package_name)
                lines.append(f"# SKIPPED: {original_line}  # built-in module")
            elif package_name.lower() in PROBLEMATIC_PACKAGES:
                replacement = PROBLEMATIC_PACKAGES[package_name.lower()]
                replaced.append(f"{package_name} -> {replacement}")
                lines.append(f"# REPLACED: {original_line}")
                for pkg in replacement.split():
                    lines.append(pkg)
            else:
                lines.append(original_line)
    except Exception as e:
        print(f"❌ Failed to read requirements.txt: {e}")
        return
    
    if skipped:
        print(f"⚠️ Skipped built-in modules: {', '.join(skipped)}")
    if replaced:
        print(f"🔄 Replaced problematic packages: {', '.join(replaced)}")
        
    if skipped or replaced:
        # Сохраняем очищенную версию
        backup_file = actual_req_file.with_suffix('.txt.backup')
        try:
            shutil.copy2(actual_req_file, backup_file)
            actual_req_file.write_text('\n'.join(lines), encoding='utf-8')
            print(f"✅ Cleaned requirements.txt (backup: {backup_file.name})")
        except Exception as e:
            print(f"❌ Failed to save cleaned requirements.txt: {e}")

def install_requirements(pip_bin):
    print("Installing essential packages first...")
    
    # Устанавливаем критически важные пакеты поэтапно
    stage1_packages = [
        "pip>=23.0",
        "setuptools>=65.0", 
        "wheel>=0.38.0",
    ]
    
    stage2_packages = [
        "cython>=0.29.0",  # может понадобиться для компиляции
        "numpy>=1.21.0",   # многие пакеты зависят от numpy
    ]
    
    stage3_packages = [
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.20.0",
        "websockets>=11.0",  
        "aiofiles>=22.0",
        "python-multipart>=0.0.6",
    ]
    
    stage4_packages = [
        "gpiozero>=1.6.0", 
        "lgpio>=0.2.0",
    ]
    
    stage5_packages = [
        # Зависимости для aiozeroconf
        "zeroconf>=0.131.0",
        "aiozeroconf>=0.1.8",
        "netifaces>=0.11.0",
        "ifaddr>=0.1.7",
    ]

    for stage_name, packages in [
        ("Core tools", stage1_packages),
        ("Build dependencies", stage2_packages), 
        ("Web framework", stage3_packages),
        ("GPIO libraries", stage4_packages),
        ("Network discovery", stage5_packages),
    ]:
        print(f"\n--- Installing {stage_name} ---")
        for pkg in packages:
            print(f"Installing {pkg}...")
            result = subprocess.run([
                pip_bin, "install", "--upgrade", pkg,
                "--no-cache-dir",  # избегаем проблем с кешем
            ], check=False)
            if result.returncode != 0:
                print(f"⚠️ Failed to install {pkg}, continuing...")

    # Теперь устанавливаем остальные requirements
    req_files = [
        INSTALL_DIR / "requirements.txt",
        INSTALL_DIR / "robot_server" / "requirements.txt",
    ]
    
    req = None
    for req_file in req_files:
        if req_file.exists():
            req = req_file
            break
    
    if req and req.exists():
        clean_requirements_txt(req)
        
        print(f"\n--- Installing requirements from {req} ---")
        result = subprocess.run([
            pip_bin, "install", "-r", str(req), 
            "--upgrade",
            "--no-cache-dir",
        ], check=False)
        
        if result.returncode != 0:
            print("⚠️ Some packages failed, trying individual installation...")
            try:
                content = safe_read_text(req)
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        package_name = line.split('==')[0].split('>=')[0].strip()
                        if package_name.lower() not in SKIP_PACKAGES:
                            print(f"Installing {package_name}...")
                            subprocess.run([pip_bin, "install", "--upgrade", line], check=False)
            except Exception as e:
                print(f"❌ Failed individual installation: {e}")
    else:
        print("⚠️ No requirements.txt found, skipping package installation")

def verify_critical_packages(pip_bin):
    """Проверяет установку критически важных пакетов"""
    print("\n--- Verifying critical packages ---")
    critical = ["fastapi", "uvicorn", "aiozeroconf", "gpiozero"]
    
    result = subprocess.run([pip_bin, "list"], capture_output=True, text=True, check=False)
    installed = result.stdout.lower() if result.returncode == 0 else ""
    
    missing = []
    for pkg in critical:
        if pkg.lower() in installed:
            print(f"✅ {pkg} installed")
        else:
            print(f"❌ {pkg} missing")
            missing.append(pkg)
    
    if missing:
        print(f"⚠️ Attempting to install missing packages: {missing}")
        for pkg in missing:
            subprocess.run([pip_bin, "install", "--upgrade", "--force-reinstall", pkg], check=False)

def install_systemd_unit():
    """Устанавливает systemd unit с правильными путями"""
    
    # Ищем service файл в разных возможных локациях
    possible_service_files = [
        INSTALL_DIR / "robot_server" / "systemd" / "lars-robot-server.service",
        INSTALL_DIR / "systemd" / "lars-robot-server.service", 
        INSTALL_DIR / "lars-robot-server.service",
    ]
    
    repo_service = None
    for service_file in possible_service_files:
        if service_file.exists():
            repo_service = service_file
            break
    
    if repo_service is None:
        print("❌ No service file found in expected locations")
        return False

    if not is_text_file(repo_service):
        print(f"❌ Service file is not a text file: {repo_service}")
        return False

    try:
        txt = safe_read_text(repo_service)
        
        # Обновляем пути в service файле для правильной структуры
        txt = txt.replace("LARS.robot_server", "robot_server")
        
        # Убеждаемся что WorkingDirectory указывает на правильную папку
        if "WorkingDirectory=" not in txt:
            # Добавляем WorkingDirectory если его нет
            lines = txt.splitlines()
            service_section_found = False
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.strip() == "[Service]":
                    service_section_found = True
                elif service_section_found and line.startswith("ExecStart="):
                    # Добавляем WorkingDirectory после ExecStart
                    new_lines.append(f"WorkingDirectory={INSTALL_DIR}")
                    service_section_found = False
            txt = "\n".join(new_lines)
        else:
            # Обновляем существующий WorkingDirectory
            txt = txt.replace("WorkingDirectory=/home/pi/LARS", f"WorkingDirectory={INSTALL_DIR}")
        
        # Обновляем путь к python в ExecStart
        venv_python = VENV_DIR / "bin" / "python"
        txt = txt.replace("/home/pi/LARS/venv/bin/python", str(venv_python))
        
        tmp = Path("/tmp/lars-robot-server.service")
        tmp.write_text(txt, encoding='utf-8')

        run_cmd(["sudo", "cp", str(tmp), str(SYSTEMD_TARGET)], check=True)
        run_cmd(["sudo", "systemctl", "daemon-reload"])
        run_cmd(["sudo", "systemctl", "enable", "lars-robot-server.service"])
        run_cmd(["sudo", "systemctl", "restart", "lars-robot-server.service"], check=False)
        print(f"✅ Service installed and enabled")
        return True
    except Exception as e:
        print(f"❌ Failed to install systemd unit: {e}")
        return False

def run_setup_wifi(python_bin):
    """Запускает setup_wifi.py из правильной локации"""
    
    setup_files = [
        INSTALL_DIR / "setup_wifi.py",
        INSTALL_DIR / "robot_server" / "setup_wifi.py",
    ]
    
    setup_script = None
    for setup_file in setup_files:
        if setup_file.exists():
            setup_script = setup_file
            break
    
    if setup_script and setup_script.exists():
        print(f"Running WiFi setup from {setup_script}...")
        subprocess.run(["sudo", python_bin, str(setup_script)], check=False)
    else:
        print("⚠️ No setup_wifi.py found, skipping WiFi setup")

def check_installation():
    """Проверяет успешность установки"""
    print("\n=== Checking installation ===")
    
    # Проверяем наличие основных файлов
    robot_server_dir = INSTALL_DIR / "robot_server"
    if robot_server_dir.exists():
        print("✅ Robot server directory created")
    else:
        print("❌ Robot server directory missing")
    
    # Проверяем venv
    if VENV_DIR.exists():
        print("✅ Virtual environment created")
        # Проверяем основные пакеты
        venv_pip = VENV_DIR / "bin" / "pip"
        if venv_pip.exists():
            result = subprocess.run([str(venv_pip), "list"], 
                                   capture_output=True, text=True, check=False)
            if "fastapi" in result.stdout.lower():
                print("✅ FastAPI installed")
            if "gpiozero" in result.stdout.lower():
                print("✅ GPIOZero installed")
    else:
        print("❌ Virtual environment missing")
    
    # Проверяем сервис
    result = subprocess.run(["sudo", "systemctl", "is-enabled", "lars-robot-server"], 
                           capture_output=True, text=True, check=False)
    if result.returncode == 0:
        print("✅ Service enabled")
    else:
        print("❌ Service not enabled")

def main():
    print("=== LARS Robot Server installer ===")
    run_cmd(["sudo", "systemctl", "stop", "lars-robot-server"], check=False)

    # Очищаем предыдущую установку
    for item in ["robot_server", "requirements.txt", "setup_wifi.py", "systemd", "VERSION"]:
        p = INSTALL_DIR / item
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    try:
        tmp_dir, app_src = download_and_extract()
        copy_app_files(app_src)

        python_choice = find_python_prefer_stable()
        install_system_dependencies() 
        venv_python, venv_pip = create_venv(python_choice)

        install_requirements(venv_pip)
        verify_critical_packages(venv_pip)
        run_setup_wifi(venv_python)

        if not install_systemd_unit():
            print("⚠️ Service unit not installed.")
        
        check_installation()

        print("\n✅ Installation completed!")
        print("\nUseful commands:")
        print("  sudo systemctl status lars-robot-server --no-pager")
        print("  sudo journalctl -u lars-robot-server -f")
        print("  sudo systemctl restart lars-robot-server")

    except Exception as e:
        print(f"❌ Installation failed: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            if 'tmp_dir' in locals():
                shutil.rmtree(tmp_dir)
        except Exception:
            pass

if __name__ == "__main__":
    main()