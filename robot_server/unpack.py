#!/usr/bin/env python3
"""
LARS Robot Server Unpacker and Installer

Downloads and unpacks robot_server snapshot from public repository,
sets up systemd service, and configures environment.

Usage:
    curl -sSL https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/unpack.py | python3 - --user robot
    
    Or locally:
    python3 unpack.py --user robot [--install-dir /home/robot/LARS]
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import venv
from pathlib import Path


PUBLIC_REPO_BASE = "https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server"
SNAPSHOT_URL = f"{PUBLIC_REPO_BASE}/robot_server_snapshot.tar.gz"
SERVICE_TEMPLATE_URL = f"{PUBLIC_REPO_BASE}/lars-robot-server.service"


def log(msg: str) -> None:
    print(f"[unpack] {msg}", flush=True)


def check_docker() -> bool:
    """Check if Docker is installed and running"""
    try:
        subprocess.run(
            ["docker", "version"],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_docker_compose() -> bool:
    """Check if Docker Compose is available"""
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def download_file(url: str, dest: Path) -> None:
    """Download file using urllib (pure Python, no external commands)"""
    log(f"Downloading {url}")
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            with open(dest, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        log(f"Downloaded to {dest}")
    except Exception as e:
        log(f"ERROR: Failed to download {url}: {e}")
        sys.exit(1)


def extract_archive(archive_path: Path, dest_dir: Path) -> None:
    """Extract tar.gz archive using tarfile module (pure Python)"""
    log(f"Extracting {archive_path} to {dest_dir}")
    try:
        with tarfile.open(archive_path, 'r:gz') as tar:
            # Security check: ensure all paths are relative
            members_to_extract = []
            for member in tar.getmembers():
                if member.name.startswith('/') or '..' in member.name:
                    log(f"WARNING: Skipping unsafe path: {member.name}")
                    continue
                members_to_extract.append(member)
            tar.extractall(path=dest_dir, members=members_to_extract)
        log(f"Extracted successfully")
    except Exception as e:
        log(f"ERROR: Failed to extract archive: {e}")
        sys.exit(1)


def restructure_extracted_files(install_dir: Path) -> None:
    """
    Restructure extracted files to match expected directory layout.
    
    The snapshot contains flat structure:
    - app/
    - config/
    - camera_daemon/
    - Dockerfile.api
    - compose.yml
    - etc.
    
    We need to create services/ structure:
    - services/api/src/app/
    - services/api/src/config/
    - services/api/Dockerfile
    - services/camera_daemon/
    """
    log("Restructuring files to match services/ layout")
    
    # Create services directory structure
    services_dir = install_dir / "services"
    services_dir.mkdir(exist_ok=True)
    
    api_dir = services_dir / "api"
    api_dir.mkdir(exist_ok=True)
    
    api_src_dir = api_dir / "src"
    api_src_dir.mkdir(exist_ok=True)
    
    # Move app/ to services/api/src/app/
    if (install_dir / "app").exists():
        log("Moving app/ to services/api/src/app/")
        if (api_src_dir / "app").exists():
            shutil.rmtree(api_src_dir / "app")
        shutil.move(str(install_dir / "app"), str(api_src_dir / "app"))
    
    # Move config/ to services/api/src/config/
    if (install_dir / "config").exists():
        log("Moving config/ to services/api/src/config/")
        if (api_src_dir / "config").exists():
            shutil.rmtree(api_src_dir / "config")
        shutil.move(str(install_dir / "config"), str(api_src_dir / "config"))
    
    # Move Dockerfile.api to services/api/Dockerfile
    if (install_dir / "Dockerfile.api").exists():
        log("Moving Dockerfile.api to services/api/Dockerfile")
        dockerfile_dest = api_dir / "Dockerfile"
        if dockerfile_dest.exists():
            dockerfile_dest.unlink()
        shutil.move(str(install_dir / "Dockerfile.api"), str(dockerfile_dest))
    
    # Move pyproject.toml and uv.lock to services/api/
    for file in ["pyproject.toml", "uv.lock"]:
        src = install_dir / file
        if src.exists():
            log(f"Moving {file} to services/api/")
            dest = api_dir / file
            if dest.exists():
                dest.unlink()
            shutil.move(str(src), str(dest))
    
    # Move camera_daemon/ to services/camera_daemon/
    if (install_dir / "camera_daemon").exists():
        log("Moving camera_daemon/ to services/camera_daemon/")
        camera_dest = services_dir / "camera_daemon"
        if camera_dest.exists():
            shutil.rmtree(camera_dest)
        shutil.move(str(install_dir / "camera_daemon"), str(camera_dest))
    
    # Create infra/nats/ structure
    if (install_dir / "nats").exists():
        log("Moving nats/ to infra/nats/")
        infra_dir = install_dir / "infra"
        infra_dir.mkdir(exist_ok=True)
        nats_dest = infra_dir / "nats"
        if nats_dest.exists():
            shutil.rmtree(nats_dest)
        shutil.move(str(install_dir / "nats"), str(nats_dest))
    
    # Create shared/ directories
    shared_dir = install_dir / "shared"
    shared_dir.mkdir(exist_ok=True)
    
    for subdir in ["data", "logs"]:
        src = install_dir / subdir
        dest = shared_dir / subdir
        if src.exists() and src.is_dir():
            log(f"Moving {subdir}/ to shared/{subdir}/")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(src), str(dest))
        else:
            dest.mkdir(exist_ok=True)
    
    log("File restructuring complete")
    
    # Verify critical paths exist
    required_paths = [
        services_dir / "api" / "Dockerfile",
        services_dir / "api" / "src" / "app",
        services_dir / "api" / "src" / "config",
        install_dir / "compose.yml",
    ]
    
    for path in required_paths:
        if not path.exists():
            log(f"ERROR: Required path missing after restructure: {path}")
            sys.exit(1)
    
    log("✓ All required paths verified")


def get_venv_python(venv_dir: Path) -> Path:
    if platform.system().lower().startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_virtualenv(install_dir: Path) -> Path:
    venv_dir = install_dir / ".venv"
    python_bin = get_venv_python(venv_dir)
    if python_bin.exists():
        log(f"Virtualenv already present: {python_bin}")
        return python_bin

    log(f"Creating virtualenv at {venv_dir}")
    venv_dir.mkdir(parents=True, exist_ok=True)
    venv.create(str(venv_dir), with_pip=True, clear=False, symlinks=True, system_site_packages=False)
    python_bin = get_venv_python(venv_dir)
    if not python_bin.exists():
        log("ERROR: virtualenv created but python executable not found")
        sys.exit(1)

    log(f"Virtualenv ready: {python_bin}")
    subprocess.run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], check=False)
    return python_bin


def render_systemd_service(template_path: Path, output_path: Path, service_user: str, install_dir: Path, python_bin: Path) -> None:
    log(f"Rendering systemd service for user={service_user}, install_dir={install_dir}")
    try:
        content = template_path.read_text(encoding="utf-8")
        content = content.replace("{{INSTALL_DIR}}", str(install_dir))
        content = content.replace("{{PYTHON_BIN}}", str(python_bin))
        content = content.replace("{{SERVICE_USER}}", service_user)

        if any(placeholder in content for placeholder in ("{{INSTALL_DIR}}", "{{PYTHON_BIN}}", "{{SERVICE_USER}}")):
            log("ERROR: some placeholders were not replaced")
            sys.exit(1)

        output_path.write_text(content, encoding="utf-8")
        log(f"Service file created at {output_path}")

        preview = output_path.read_text(encoding="utf-8").splitlines()[:15]
        log("Generated service file preview:")
        for line in preview:
            log(f"  {line}")
    except Exception as e:
        log(f"ERROR: Failed to render service file: {e}")
        sys.exit(1)


def copy_file_with_sudo(src: Path, dest: Path) -> bool:
    """Copy file to system location using sudo (only subprocess call needed)"""
    try:
        subprocess.run(
            ["sudo", "cp", str(src), str(dest)],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"ERROR: Failed to copy {src} to {dest}: {e.stderr}")
        return False


def systemd_daemon_reload() -> bool:
    """Reload systemd daemon (only subprocess call needed)"""
    try:
        subprocess.run(
            ["sudo", "systemctl", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"ERROR: Failed to reload systemd: {e.stderr}")
        return False


def systemd_enable_service(service_name: str) -> bool:
    """Enable systemd service (only subprocess call needed)"""
    try:
        subprocess.run(
            ["sudo", "systemctl", "enable", service_name],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"ERROR: Failed to enable service: {e.stderr}")
        return False


def systemd_start_service(service_name: str) -> bool:
    """Start systemd service (only subprocess call needed)"""
    try:
        subprocess.run(
            ["sudo", "systemctl", "start", service_name],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"ERROR: Failed to start service: {e.stderr}")
        return False


def install_systemd_service(service_file: Path) -> None:
    """Install systemd service file"""
    log("Installing systemd service")
    
    dest = Path("/etc/systemd/system/lars-robot-server.service")
    
    if not copy_file_with_sudo(service_file, dest):
        log("ERROR: Failed to install systemd service")
        sys.exit(1)
    
    if not systemd_daemon_reload():
        log("ERROR: Failed to reload systemd daemon")
        sys.exit(1)
    
    log("Systemd service installed")


def verify_install_dir(install_dir: Path, service_user: str) -> None:
    """Verify installation directory exists and has correct permissions"""
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if we can write to the directory
        test_file = install_dir / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            log(f"WARNING: No write permission to {install_dir}")
            log(f"You may need to run: sudo chown -R {service_user}:{service_user} {install_dir}")
    except Exception as e:
        log(f"ERROR: Failed to create installation directory: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="LARS Robot Server Unpacker")
    parser.add_argument("--user", required=True, help="System user to run the service")
    parser.add_argument("--install-dir", help="Installation directory (default: /home/<user>/LARS)")
    parser.add_argument("--enable", action="store_true", help="Enable and start systemd service after install")
    parser.add_argument("--skip-systemd", action="store_true", help="Skip systemd service installation")
    parser.add_argument("--skip-docker-check", action="store_true", help="Skip Docker prerequisite check")
    
    args = parser.parse_args()
    
    service_user = args.user
    install_dir = Path(args.install_dir) if args.install_dir else Path(f"/home/{service_user}/LARS")
    
    log(f"Installing LARS Robot Server")
    log(f"  User: {service_user}")
    log(f"  Install dir: {install_dir}")
    
    # Check Docker prerequisites
    if not args.skip_docker_check:
        log("Checking Docker prerequisites...")
        if not check_docker():
            log("ERROR: Docker is not installed or not running")
            log("Please install Docker: https://docs.docker.com/engine/install/")
            sys.exit(1)
        if not check_docker_compose():
            log("ERROR: Docker Compose is not available")
            log("Please install Docker Compose v2")
            sys.exit(1)
        log("Docker prerequisites OK")
    
    # Verify installation directory
    verify_install_dir(install_dir, service_user)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Download snapshot archive
        archive_path = tmppath / "robot_server_snapshot.tar.gz"
        download_file(SNAPSHOT_URL, archive_path)
        
        # Extract archive to installation directory
        extract_archive(archive_path, install_dir)
        
        # Restructure files to match services/ layout
        restructure_extracted_files(install_dir)
        
        python_bin = ensure_virtualenv(install_dir)
        
        if not args.skip_systemd:
            # Download and render systemd service
            service_template = tmppath / "lars-robot-server.service"
            download_file(SERVICE_TEMPLATE_URL, service_template)
            
            service_output = tmppath / "lars-robot-server-rendered.service"
            render_systemd_service(service_template, service_output, service_user, install_dir, python_bin)
            
            # Install systemd service
            install_systemd_service(service_output)
            
            if args.enable:
                log("Enabling and starting service")
                
                if systemd_enable_service("lars-robot-server.service"):
                    log("Service enabled")
                else:
                    log("WARNING: Failed to enable service")
                
                if systemd_start_service("lars-robot-server.service"):
                    log("Service started")
                else:
                    log("WARNING: Failed to start service")
    
    if not args.skip_systemd:
        log("Check service: sudo systemctl status lars-robot-server")


if __name__ == "__main__":
    main()