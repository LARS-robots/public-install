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
from datetime import datetime
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
    
        # Create symlink at root config/ for compose.yml volume mount
        # compose.yml expects ./config:/app/src/config:ro
        root_config_link = install_dir / "config"
        if not root_config_link.exists():
            log("Creating symlink config/ -> services/api/src/config/")
            root_config_link.symlink_to("services/api/src/config")
    
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
    
    # Move motor_daemon/ to services/motor_daemon/
    if (install_dir / "motor_daemon").exists():
        log("Moving motor_daemon/ to services/motor_daemon/")
        motor_dest = services_dir / "motor_daemon"
        if motor_dest.exists():
            shutil.rmtree(motor_dest)
        shutil.move(str(install_dir / "motor_daemon"), str(motor_dest))
    
    # Move logger/ to services/logger/ (if exists in flat structure)
    if (install_dir / "logger").exists():
        log("Moving logger/ to services/logger/")
        logger_dest = services_dir / "logger"
        if logger_dest.exists():
            shutil.rmtree(logger_dest)
        shutil.move(str(install_dir / "logger"), str(logger_dest))
    
    # Move nats_logger/ to services/nats_logger/ (if exists in flat structure)
    if (install_dir / "nats_logger").exists():
        log("Moving nats_logger/ to services/nats_logger/")
        nats_logger_dest = services_dir / "nats_logger"
        if nats_logger_dest.exists():
            shutil.rmtree(nats_logger_dest)
        shutil.move(str(install_dir / "nats_logger"), str(nats_logger_dest))
    
    # Handle services/ structure (if already in services/ from snapshot)
    # This handles the case where workflow copies directly to services/logger/ and services/nats_logger/
    if (install_dir / "services" / "logger").exists():
        log("✓ Logger daemon found in services/logger/")
    if (install_dir / "services" / "nats_logger").exists():
        log("✓ nats_logger found in services/nats_logger/")
    
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
    
    # Verify camera daemon critical paths exist
    camera_daemon_paths = [
        services_dir / "camera_daemon" / "Dockerfile",
        services_dir / "camera_daemon" / "Dockerfile.rpi",
        services_dir / "camera_daemon" / "main.py",
        services_dir / "camera_daemon" / "requirements.txt",
    ]
    
    missing_camera_files = []
    for path in camera_daemon_paths:
        if not path.exists():
            missing_camera_files.append(path)
    
    if missing_camera_files:
        log("WARNING: Some camera daemon files are missing:")
        for path in missing_camera_files:
            log(f"  - {path}")
    else:
        log("✓ All camera daemon files verified")
    
    # Verify compose override files exist (optional but should be present)
    compose_overrides = [
        services_dir / "camera_daemon" / "compose.rpi.yml",
        services_dir / "camera_daemon" / "compose.linux.yml",
        services_dir / "camera_daemon" / "compose.windows.yml",
    ]
    
    found_overrides = []
    for path in compose_overrides:
        if path.exists():
            found_overrides.append(path.name)
    
    if found_overrides:
        log(f"✓ Found compose override files: {', '.join(found_overrides)}")
    else:
        log("WARNING: No compose override files found in camera_daemon/")


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


def systemd_stop_service(service_name: str) -> bool:
    """Stop systemd service (only subprocess call needed)"""
    try:
        subprocess.run(
            ["sudo", "systemctl", "stop", service_name],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError:
        # Service might not be running, that's OK
        return False


def systemd_disable_service(service_name: str) -> bool:
    """Disable systemd service (only subprocess call needed)"""
    try:
        subprocess.run(
            ["sudo", "systemctl", "disable", service_name],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError:
        # Service might not be enabled, that's OK
        return False


def remove_old_systemd_service() -> None:
    """Remove old systemd service before installing new one"""
    service_path = Path("/etc/systemd/system/lars-robot-server.service")
    
    if not service_path.exists():
        log("No existing systemd service found")
        return
    
    log("Found existing systemd service, removing it...")
    
    # Stop the service if running
    log("Stopping old service...")
    systemd_stop_service("lars-robot-server.service")
    
    # Disable the service
    log("Disabling old service...")
    systemd_disable_service("lars-robot-server.service")
    
    # Remove the service file
    try:
        subprocess.run(
            ["sudo", "rm", "-f", str(service_path)],
            check=True,
            capture_output=True,
            text=True
        )
        log("Old service file removed")
    except subprocess.CalledProcessError as e:
        log(f"WARNING: Failed to remove old service file: {e.stderr}")
    
    # Reset failed state (clear any cached errors)
    try:
        subprocess.run(
            ["sudo", "systemctl", "reset-failed", "lars-robot-server.service"],
            check=False,  # Don't fail if service doesn't exist
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError:
        pass
    
    # Reload systemd to clear cache
    if systemd_daemon_reload():
        log("Systemd daemon reloaded (old service removed)")


def install_systemd_service(service_file: Path) -> None:
    """Install systemd service file"""
    log("Installing new systemd service")
    
    # First, remove any old service
    remove_old_systemd_service()
    
    dest = Path("/etc/systemd/system/lars-robot-server.service")
    
    if not copy_file_with_sudo(service_file, dest):
        log("ERROR: Failed to install systemd service")
        sys.exit(1)
    
    if not systemd_daemon_reload():
        log("ERROR: Failed to reload systemd daemon")
        sys.exit(1)
    
    log("✓ New systemd service installed successfully")


def detect_robot_type(install_dir: Path, cli_override: str | None = None, no_heuristics: bool = False) -> tuple[str, str]:
    """
    Detect robot type with precedence:
    1. CLI flag (--robot-type)
    2. Config files (motor_daemon/config.toml, then API config)
    3. Hardware heuristics (if not disabled)
    
    Returns: (robot_type, detection_source)
    """
    SUPPORTED_TYPES = ("simulator", "raspbot", "diktum")
    
    # 1. CLI override (highest priority)
    if cli_override:
        robot_type = cli_override.lower().strip()
        if robot_type not in SUPPORTED_TYPES:
            log(f"ERROR: Invalid robot type '{robot_type}'. Supported: {', '.join(SUPPORTED_TYPES)}")
            sys.exit(1)
        return robot_type, "CLI flag"
    
    # 2. Check config files (motor_daemon/config.toml first, then API config)
    config_paths = [
        install_dir / "services" / "motor_daemon" / "config.toml",
        install_dir / "services" / "api" / "src" / "config" / "config.toml",
        install_dir / "config.toml",
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                try:
                    import tomllib
                except ImportError:
                    import tomli as tomllib
                
                with open(config_path, "rb") as f:
                    config = tomllib.load(f)
                    default_section = config.get("default", {})
                    robot_type = default_section.get("robot_type", "").lower().strip()
                    if robot_type in SUPPORTED_TYPES:
                        return robot_type, f"config file ({config_path.relative_to(install_dir)})"
            except Exception as e:
                log(f"WARNING: Could not read robot_type from {config_path}: {e}")
                continue
    
    # 3. Hardware heuristics (if enabled)
    if not no_heuristics:
        # Check for Raspberry Pi
        try:
            model_path = Path("/proc/device-tree/model")
            if model_path.exists():
                model_text = model_path.read_text().lower()
                if "raspberry pi" in model_text:
                    # Default to diktum for RPi (most common)
                    return "diktum", "hardware detection (Raspberry Pi)"
            
            cpuinfo_path = Path("/proc/cpuinfo")
            if cpuinfo_path.exists():
                cpuinfo_text = cpuinfo_path.read_text().lower()
                if "raspberry pi" in cpuinfo_text:
                    return "diktum", "hardware detection (Raspberry Pi)"
        except Exception:
            pass
    
    # Default fallback
    return "simulator", "default fallback"


def write_robot_env(robot_type: str, detection_source: str) -> bool:
    """
    Write robot type to /etc/lars/robot.env.
    Creates directory if missing, backs up existing file if malformed.
    Returns True on success, False on failure.
    """
    env_dir = Path("/etc/lars")
    env_file = env_dir / "robot.env"
    
    # Create directory if missing
    try:
        env_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    except PermissionError:
        log(f"ERROR: Cannot create {env_dir}. Run with sudo.")
        return False
    except Exception as e:
        log(f"ERROR: Failed to create {env_dir}: {e}")
        return False
    
    # Check if existing file is valid
    if env_file.exists():
        try:
            existing_content = env_file.read_text(encoding="utf-8").strip()
            existing_type = None
            for line in existing_content.splitlines():
                if line.startswith("ROBOT_TYPE="):
                    existing_type = line.split("=", 1)[1].strip().strip('"\'')
                    break
            
            # If existing file has same value, skip write (idempotent)
            if existing_type == robot_type:
                log(f"✓ Robot type already set to '{robot_type}' in {env_file}")
                return True
            
            # Backup existing file if different
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_file = env_dir / f"robot.env.bak.{timestamp}"
            try:
                shutil.copy2(env_file, backup_file)
                log(f"Backed up existing {env_file} to {backup_file}")
            except Exception as e:
                log(f"WARNING: Could not backup existing env file: {e}")
        except Exception as e:
            log(f"WARNING: Could not read existing {env_file}: {e}")
            # Backup malformed file
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_file = env_dir / f"robot.env.bak.{timestamp}"
            try:
                shutil.copy2(env_file, backup_file)
                log(f"Backed up malformed {env_file} to {backup_file}")
            except Exception:
                pass
    
    # Write new env file
    try:
        content = f"# Robot type detected by: {detection_source}\n"
        content += f"ROBOT_TYPE={robot_type}\n"
        env_file.write_text(content, encoding="utf-8")
        # Set strict permissions (readable by all, writable by root only)
        env_file.chmod(0o644)
        log(f"✓ Wrote ROBOT_TYPE={robot_type} to {env_file} (detected via: {detection_source})")
        return True
    except PermissionError:
        log(f"ERROR: Cannot write to {env_file}. Run with sudo.")
        return False
    except Exception as e:
        log(f"ERROR: Failed to write {env_file}: {e}")
        return False


def verify_install_dir(install_dir: Path, service_user: str) -> None:
    """Verify installation directory exists and has correct permissions"""
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if we can write to the directory
        test_file = install_dir / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
            log(f"✓ Write permission verified for {install_dir}")
        except PermissionError:
            log(f"ERROR: No write permission to {install_dir}")
            log(f"You need to fix permissions:")
            log(f"  sudo chown -R {service_user}:{service_user} {install_dir}")
            log(f"Or if the directory doesn't exist yet:")
            log(f"  sudo mkdir -p {install_dir}")
            log(f"  sudo chown -R {service_user}:{service_user} {install_dir}")
            sys.exit(1)
    except Exception as e:
        log(f"ERROR: Failed to create installation directory: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="LARS Robot Server Unpacker")
    parser.add_argument("--user", required=True, help="System user to run the service")
    parser.add_argument("--install-dir", help="Installation directory (default: /home/<user>/LARS)")
    parser.add_argument("--robot-type", help="Override robot type (simulator|raspbot|diktum)")
    parser.add_argument("--no-heuristics", action="store_true", help="Disable hardware detection fallback")
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
        log("✓ Docker prerequisites OK")
    
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
        
        # Detect robot type and write to /etc/lars/robot.env
        log("Detecting robot type...")
        robot_type, detection_source = detect_robot_type(install_dir, args.robot_type, args.no_heuristics)
        log(f"Detected robot type: {robot_type} (via {detection_source})")
        
        if not write_robot_env(robot_type, detection_source):
            log("ERROR: Failed to write robot type configuration")
            sys.exit(1)
        
        python_bin = ensure_virtualenv(install_dir)
        
        if not args.skip_systemd:
            # Download and render systemd service
            service_template = tmppath / "lars-robot-server.service"
            download_file(SERVICE_TEMPLATE_URL, service_template)
            
            service_output = tmppath / "lars-robot-server-rendered.service"
            render_systemd_service(service_template, service_output, service_user, install_dir, python_bin)
            
            # Install systemd service (this will remove old one first)
            install_systemd_service(service_output)
            
            # Reload systemd to pick up new env file
            if systemd_daemon_reload():
                log("✓ Systemd daemon reloaded")
            else:
                log("WARNING: Failed to reload systemd daemon")
            
            if args.enable:
                log("Enabling and starting service")
                
                if systemd_enable_service("lars-robot-server.service"):
                    log("✓ Service enabled")
                else:
                    log("WARNING: Failed to enable service")
                
                # Try to restart if already running, otherwise start
                try:
                    result = subprocess.run(
                        ["sudo", "systemctl", "is-active", "lars-robot-server.service"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        # Service is running, restart it
                        subprocess.run(
                            ["sudo", "systemctl", "try-restart", "lars-robot-server.service"],
                            check=False,
                            capture_output=True
                        )
                        log("✓ Service restarted")
                    else:
                        # Service not running, start it
                        if systemd_start_service("lars-robot-server.service"):
                            log("✓ Service started")
                        else:
                            log("WARNING: Failed to start service")
                except Exception as e:
                    log(f"WARNING: Could not check/restart service: {e}")
                    if systemd_start_service("lars-robot-server.service"):
                        log("✓ Service started")
                    else:
                        log("WARNING: Failed to start service")
    
    if not args.skip_systemd:
        log("1. Check service: sudo systemctl status lars-robot-server")
        log("2. View logs: sudo journalctl -fu lars-robot-server")
        log(f"3. Robot type: {robot_type} (configured in /etc/lars/robot.env)")


if __name__ == "__main__":
    main()