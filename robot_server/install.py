#!/usr/bin/env python3
"""
LARS Robot Server Installer (версии без pigpio/pigpiod)

Этот установщик:
 - скачивает архив robot_server,
 - копирует файлы приложения в ~/LARS/robot_server,
 - создает Python venv (предпочтительно python3.11),
 - устанавливает requirements + gpiozero + lgpio в venv,
 - ставит системные пакеты gpiozero + lgpio,
 - запускает setup_wifi.py (best-effort),
 - копирует systemd/lars-robot-server.service в /etc/systemd/system,
   заменяя "LARS.robot_server" на "robot_server" при необходимости,
 - включает и запускает сервис.
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


def find_python_prefer_311():
    """Находит подходящую версию Python, предпочтительно 3.10 для совместимости"""
    candidates = [
        "/usr/bin/python3.10",  # более совместимая версия
        "/usr/bin/python3.9",   # ещё более старая, но стабильная
        "/usr/bin/python3.11",
        "/usr/bin/python3",
        shutil.which("python3") or "/usr/bin/python3",
    ]
    
    for c in candidates:
        if c and Path(c).exists():
            # Проверим версию
            try:
                result = subprocess.run([c, "--version"], capture_output=True, text=True)
                version_str = result.stdout.strip()
                print(f"Found Python: {c} ({version_str})")
                return str(c)
            except Exception:
                continue
    
    print("❌ No Python found; please install python3.")
    sys.exit(1)


def create_venv(python_bin):
    if VENV_DIR.exists():
        print("Removing existing venv:", VENV_DIR)
        shutil.rmtree(VENV_DIR)
    print("Creating venv with", python_bin)
    subprocess.run([python_bin, "-m", "venv", str(VENV_DIR)], check=True)
    
    # Обновляем pip в venv до последней версии
    venv_pip = str(VENV_DIR / "bin" / "pip")
    print("Upgrading pip in venv...")
    subprocess.run([venv_pip, "install", "--upgrade", "pip", "setuptools", "wheel"], check=False)
    
    return str(VENV_DIR / "bin" / "python"), venv_pip


def copy_app_files(app_src):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    dest = INSTALL_DIR / "robot_server"
    if dest.exists():
        shutil.rmtree(dest)
    print("Copying app to", dest)
    shutil.copytree(app_src, dest)

    # Копирование дополнительных файлов
    for name in ["requirements.txt", "setup_wifi.py", "VERSION"]:
        src_parent = app_src.parent / name
        src_self = app_src / name
        
        if src_parent.exists():
            src = src_parent
        elif src_self.exists():
            src = src_self
        else:
            continue
            
        try:
            shutil.copy2(src, INSTALL_DIR / name)
            print(f"  Copied: {name}")
        except Exception as e:
            print(f"  ⚠️ Failed to copy {name}: {e}")

    # Копирование systemd файлов
    src_systemd = app_src.parent / "systemd"
    if src_systemd.exists():
        dest_systemd = INSTALL_DIR / "systemd"
        if dest_systemd.exists():
            shutil.rmtree(dest_systemd)
        try:
            shutil.copytree(src_systemd, dest_systemd)
            print("  Copied: systemd/")
        except Exception as e:
            print(f"  ⚠️ Failed to copy systemd/: {e}")


def install_gpio_libs():
    print("Installing gpiozero + lgpio system-wide")
    run_cmd(["sudo", "apt", "update"], check=True)
    run_cmd(["sudo", "apt", "install", "-y", 
             "python3-gpiozero", "python3-lgpio", "gpiod", 
             "python3-pip", "python3-dev", "python3-setuptools"], check=True)


def clean_requirements_txt(req_file):
    """Очищает requirements.txt от проблемных пакетов"""
    if not req_file.exists():
        print(f"  ⚠️ Requirements file not found: {req_file}")
        return
    
    if not is_text_file(req_file):
        print(f"  ⚠️ Requirements file is not a text file: {req_file}")
        return
    
    print("Cleaning requirements.txt...")
    lines = []
    skipped = []
    
    try:
        content = safe_read_text(req_file)
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                lines.append(line)
                continue
            
            # Извлекаем имя пакета (до == или >= и т.д.)
            package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].strip()
            
            if package_name.lower() in SKIP_PACKAGES:
                skipped.append(package_name)
                lines.append(f"# SKIPPED: {line}  # built-in module")
            else:
                lines.append(line)
    except Exception as e:
        print(f"  ❌ Failed to read requirements.txt: {e}")
        return
    
    if skipped:
        print(f"  ⚠️ Skipped built-in modules: {', '.join(skipped)}")
        # Сохраняем очищенную версию
        backup_file = req_file.with_suffix('.txt.backup')
        try:
            shutil.copy2(req_file, backup_file)
            req_file.write_text('\n'.join(lines), encoding='utf-8')
            print(f"  ✅ Cleaned requirements.txt (backup: {backup_file.name})")
        except Exception as e:
            print(f"  ❌ Failed to save cleaned requirements.txt: {e}")


def install_requirements(pip_bin):
    print("Installing essential packages first...")
    # Ставим основные пакеты сначала
    essential_packages = [
        "gpiozero", 
        "lgpio",
        "fastapi",
        "uvicorn[standard]",
        "websockets",
        "aiofiles",
        "python-multipart",
    ]
    
    for pkg in essential_packages:
        print(f"Installing {pkg}...")
        result = subprocess.run([pip_bin, "install", pkg], check=False)
        if result.returncode != 0:
            print(f"  ⚠️ Failed to install {pkg}, continuing...")

    req = INSTALL_DIR / "requirements.txt"
    if req.exists():
        # Очищаем requirements от проблемных пакетов
        clean_requirements_txt(req)
        
        print("Installing remaining requirements from", req)
        # Установка с игнорированием ошибок для проблемных пакетов
        result = subprocess.run([
            pip_bin, "install", "-r", str(req), 
            "--no-deps",  # не устанавливаем зависимости автоматически
            "--force-reinstall"
        ], check=False)
        
        if result.returncode != 0:
            print("  ⚠️ Some packages failed to install, trying individual installation...")
            # Пробуем установить пакеты по одному
            try:
                content = safe_read_text(req)
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        package_name = line.split('==')[0].split('>=')[0].strip()
                        if package_name.lower() not in SKIP_PACKAGES:
                            print(f"  Installing {package_name}...")
                            subprocess.run([pip_bin, "install", line], check=False)
            except Exception as e:
                print(f"  ❌ Failed to read requirements for individual installation: {e}")


def run_setup_wifi(python_bin):
    setup_script = INSTALL_DIR / "setup_wifi.py"
    if setup_script.exists():
        print("Running WiFi setup...")
        subprocess.run(["sudo", python_bin, str(setup_script)], check=False)


def install_systemd_unit():
    repo_service = INSTALL_DIR / "systemd" / "lars-robot-server.service"
    if not repo_service.exists():
        print("❌ No service file found at", repo_service)
        return False

    if not is_text_file(repo_service):
        print(f"❌ Service file is not a text file: {repo_service}")
        return False

    try:
        txt = safe_read_text(repo_service)
        txt = txt.replace("LARS.robot_server", "robot_server")  # normalize import path if needed

        tmp = Path("/tmp/lars-robot-server.service")
        tmp.write_text(txt, encoding='utf-8')

        run_cmd(["sudo", "cp", str(tmp), str(SYSTEMD_TARGET)], check=True)
        run_cmd(["sudo", "systemctl", "daemon-reload"])
        run_cmd(["sudo", "systemctl", "enable", "lars-robot-server.service"])
        run_cmd(["sudo", "systemctl", "restart", "lars-robot-server.service"], check=False)
        return True
    except Exception as e:
        print(f"❌ Failed to install systemd unit: {e}")
        return False


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

        python_choice = find_python_prefer_311()
        venv_python, venv_pip = create_venv(python_choice)

        install_gpio_libs()
        install_requirements(venv_pip)
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
        # Очистка временных файлов
        try:
            if 'tmp_dir' in locals():
                shutil.rmtree(tmp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    main()