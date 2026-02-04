#!/usr/bin/env python3
"""Downloads and extracts latest snapshot of robot server"""
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import subprocess
from pathlib import Path

URL = "https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/robot_server_snapshot.tar.gz"

def restructure(d: Path):
    """Restructure extracted files to services/ layout."""
    s = d / "services"
    s.mkdir(exist_ok=True)
    api, api_src = s / "api", s / "api" / "src"
    api_src.mkdir(parents=True, exist_ok=True)
    
    # Move API files (config and env stay in root)
    for src, dst in [
        (d / "app", api_src / "app"),
        (d / "Dockerfile.api", api / "Dockerfile"),
        (d / "ui_dist", api_src / "app" / "ui_dist"),
    ]:
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
            shutil.move(str(src), str(dst))
            
    # Update config and env (overwrite existing)
    for dirname in ["config", "env"]:
        src = d / dirname
        if src.exists():
            dst = d / dirname  # Stay in root
            if dst.exists() and dst != src:  # If already exists separately
                shutil.rmtree(dst)
            if src != dst:  # Only move if different
                shutil.move(str(src), str(dst))
    
    for f in ["pyproject.toml", "uv.lock"]:
        if (d / f).exists():
            shutil.move(str(d / f), str(api / f))
    
    # Move daemons
    for daemon in ["camera_daemon", "motor_daemon", "logger", "nats_logger"]:
        if (d / daemon).exists():
            dst = s / daemon
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(d / daemon), str(dst))
    
    # Handle services/ structure (if already there from snapshot)
    if (d / "services").exists():
        for item in (d / "services").iterdir():
            if item.is_dir() and not (s / item.name).exists():
                shutil.move(str(item), str(s / item.name))
    
    # Move nats to infra/
    if (d / "nats").exists():
        (d / "infra").mkdir(exist_ok=True)
        shutil.move(str(d / "nats"), str(d / "infra" / "nats"))
    
    # Move data/logs to shared/ (best-effort, don't fail update on permissions)
    shared = d / "shared"
    shared.mkdir(exist_ok=True)
    for subdir in ["data", "logs"]:
        src = d / subdir
        if not src.exists():
            continue

        dst = shared / subdir
        if dst.exists():
            try:
                shutil.rmtree(dst)
            except PermissionError:
                print(f"[update] ! No permission to remove {dst}; skipping move for {subdir}")
                try:
                    shutil.rmtree(src)
                except Exception:
                    pass
                continue
            except Exception as e:
                print(f"[update] ! Failed to remove {dst}: {e}; skipping move for {subdir}")
                try:
                    shutil.rmtree(src)
                except Exception:
                    pass
                continue

        try:
            shutil.move(str(src), str(dst))
        except PermissionError:
            print(f"[update] ! No permission to move {src} -> {dst}; leaving as-is")
        except Exception as e:
            print(f"[update] ! Failed to move {src} -> {dst}: {e}")

    (shared / "data").mkdir(exist_ok=True)
    (shared / "logs").mkdir(exist_ok=True)


def _render_service_template(template_path: Path, service_user: str, install_dir: Path) -> str:
    content = template_path.read_text(encoding="utf-8")
    return (
        content.replace("{{SERVICE_USER}}", service_user)
        .replace("{{INSTALL_DIR}}", str(install_dir))
    )


def install_systemd_services(install_dir: Path) -> None:
    """Install systemd service templates to /etc/systemd/system (best-effort)."""
    service_user = os.getenv("SUDO_USER") or os.getenv("USER") or os.getenv("USERNAME") or "robot"
    templates = [
        ("lars-robot-server.service", "LARS Robot Server"),
        ("lars-updater.service", "LARS Update Daemon"),
    ]

    # Templates are expected at install root (copied by snapshot)
    missing = []
    for filename, _ in templates:
        if not (install_dir / filename).exists():
            missing.append(filename)

    if missing:
        print(f"[update] ! Missing systemd templates: {', '.join(missing)}")

    if os.geteuid() != 0:
        print("[update] ! Not running as root; skipping systemd install.")
        print("[update]   To install services manually:")
        for filename, _ in templates:
            print(f"[update]   sudo cp {install_dir / filename} /etc/systemd/system/{filename}")
        print("[update]   sudo systemctl daemon-reload")
        print("[update]   sudo systemctl enable --now lars-robot-server lars-updater")
        return

    for filename, label in templates:
        template_path = install_dir / filename
        if not template_path.exists():
            continue
        try:
            rendered = _render_service_template(template_path, service_user, install_dir)
            dst = Path("/etc/systemd/system") / filename
            dst.write_text(rendered, encoding="utf-8")
            print(f"[update] ✓ Installed systemd unit: {label} ({dst})")
        except Exception as e:
            print(f"[update] ! Failed to install {filename}: {e}")

    # Try reload (best-effort)
    try:
        subprocess.run(["systemctl", "daemon-reload"], check=False)
    except Exception:
        pass

if __name__ == "__main__":
    # Auto-detect install directory: use arg, or default to /home/{user}/LARS
    if len(sys.argv) > 1:
        install_dir = Path(sys.argv[1])
    else:
        user = os.getenv("USER") or os.getenv("USERNAME") or "robot"
        install_dir = Path(f"/home/{user}/LARS")
    
    print(f"[update] Updating code in {install_dir}")
    
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "snapshot.tar.gz"
        print(f"[update] Downloading snapshot...")
        urllib.request.urlretrieve(URL, archive)
        
        print(f"[update] Extracting...")
        with tarfile.open(archive, 'r:gz') as tar:
            tar.extractall(install_dir)
        
        print(f"[update] Restructuring files...")
        restructure(install_dir)

        print(f"[update] Installing systemd services...")
        install_systemd_services(install_dir)
        
        print(f"[update] ✓ Update complete")
