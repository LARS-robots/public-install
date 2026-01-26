#!/usr/bin/env python3
"""Downloads and extracts latest snapshot of robot server"""
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/robot_server_snapshot.tar.gz"

def restructure(d: Path):
    """Restructure extracted files to services/ layout."""
    s = d / "services"
    s.mkdir(exist_ok=True)
    api, api_src = s / "api", s / "api" / "src"
    api_src.mkdir(parents=True, exist_ok=True)
    
    # Move API files
    for src, dst in [
        (d / "app", api_src / "app"),
        (d / "config", api_src / "config"),
        (d / "Dockerfile.api", api / "Dockerfile"),
        (d / "ui_dist", api_src / "app" / "ui_dist"),
    ]:
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
            shutil.move(str(src), str(dst))
    
    for f in ["pyproject.toml", "uv.lock"]:
        if (d / f).exists():
            shutil.move(str(d / f), str(api / f))
    
    # Config symlink
    if not (d / "config").exists() and (api_src / "config").exists():
        (d / "config").symlink_to("services/api/src/config")
    
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
    
    # Move data/logs to shared/
    shared = d / "shared"
    shared.mkdir(exist_ok=True)
    for subdir in ["data", "logs"]:
        if (d / subdir).exists():
            shutil.move(str(d / subdir), str(shared / subdir))
        else:
            (shared / subdir).mkdir(exist_ok=True)

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
        
        print(f"[update] ✓ Update complete")