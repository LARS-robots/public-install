#!/usr/bin/env python3
"""
LARS Robot Server Installer — use existing systemd unit from repo
This installer:
 - downloads robot_server archive,
 - copies application files into ~/LARS/robot_server,
 - creates a Python venv (prefer python3.11),
 - installs requirements in the venv,
 - runs setup_wifi.py (best-effort),
 - takes existing ~/LARS/systemd/lars-robot-server.service, patches it (WorkingDirectory, PYTHONPATH, ExecStart -> venv python),
 - writes it to /etc/systemd/system/lars-robot-server.service (overwrites), daemon-reload, enable & start.
"""
from pathlib import Path
import urllib.request
import tarfile
import tempfile
import shutil
import subprocess
import sys
import os
import re

# -------- CONFIG --------
GITHUB_REPO = "LARS-robots/public-install"
ARCHIVE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/robot_server/robot_server.tar.gz"
INSTALL_DIR = Path.home() / "LARS"
VENV_DIR = INSTALL_DIR / "venv"
SYSTEMD_TARGET = Path("/etc/systemd/system/lars-robot-server.service")
# relative path inside extracted archive that usually contains service:
SYSTEMD_RELPATH = Path("systemd") / "lars-robot-server.service"

# -------- helpers --------
def run_cmd(cmd, check=True, sudo=False):
    """
    Run a command.
    cmd: list[str] or str
    if sudo=True and not root, prefix with sudo
    returns (rc, stdout, stderr)
    """
    if sudo and os.geteuid() != 0:
        if isinstance(cmd, list):
            cmd = ["sudo"] + cmd
        else:
            cmd = "sudo " + cmd
    print("▶", cmd if isinstance(cmd, str) else " ".join(cmd))
    try:
        proc = subprocess.run(cmd, shell=not isinstance(cmd, list),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        if out:
            print(out)
        if err:
            print(err)
        return proc.returncode, out, err
    except subprocess.CalledProcessError as e:
        stdout = getattr(e, "stdout", "") or ""
        stderr = getattr(e, "stderr", "") or ""
        print("❌ Command failed:", e)
        if stdout.strip():
            print(stdout.strip())
        if stderr.strip():
            print(stderr.strip())
        return e.returncode, stdout, stderr


def download_and_extract():
    """Download the tar.gz to a temp dir and extract it. Return (tmpdir, app_dir)."""
    tmp = Path(tempfile.mkdtemp())
    archive = tmp / "robot_server.tar.gz"
    print("Downloading", ARCHIVE_URL)
    try:
        req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "LARS-installer"})
        with urllib.request.urlopen(req) as r, open(archive, "wb") as f:
            f.write(r.read())
    except Exception as e:
        print("❌ Download failed:", e)
        sys.exit(1)

    try:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp)
    except Exception as e:
        print("❌ Extraction failed:", e)
        sys.exit(1)

    # Determine app directory inside extracted archive
    # common possibilities:
    if (tmp / "app").exists():
        app_dir = tmp / "app"
    elif (tmp / "robot_server").exists():
        app_dir = tmp / "robot_server"
    else:
        # fallback to tmp root (may contain the app files directly)
        app_dir = tmp

    print("Archive extracted to:", tmp)
    return tmp, app_dir


def find_python_prefer_311():
    """Prefer python3.11, fall back to python3."""
    candidates = ["/usr/bin/python3.11", "/usr/bin/python3", shutil.which("python3") or "/usr/bin/python3"]
    for c in candidates:
        if c and Path(c).exists():
            print("Using python:", c)
            return str(c)
    print("❌ No Python found; please install python3.")
    sys.exit(1)


def create_venv(python_bin):
    """Create a clean venv at VENV_DIR using python_bin. Return (python_in_venv, pip_in_venv)."""
    if VENV_DIR.exists():
        print("Removing existing venv:", VENV_DIR)
        shutil.rmtree(VENV_DIR)
    print("Creating venv with", python_bin)
    rc, _, _ = run_cmd([python_bin, "-m", "venv", str(VENV_DIR)], check=False)
    if rc != 0:
        print("❌ Failed to create virtualenv")
        sys.exit(1)
    python_in_venv = VENV_DIR / "bin" / "python"
    pip_in_venv = VENV_DIR / "bin" / "pip"
    # upgrade pip best-effort
    print("Upgrading pip (best-effort)...")
    run_cmd([str(pip_in_venv), "install", "--upgrade", "pip"], check=False)
    return str(python_in_venv), str(pip_in_venv)


def copy_app_files(app_src):
    """Copy application files from app_src into INSTALL_DIR/robot_server."""
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    dest = INSTALL_DIR / "robot_server"
    if dest.exists():
        print("Removing old app directory:", dest)
        shutil.rmtree(dest)
    print("Copying app from", app_src, "to", dest)
    shutil.copytree(app_src, dest)

    # copy top-level files from archive root to INSTALL_DIR if present
    for name in ["requirements.txt", "setup_wifi.py", "VERSION"]:
        src = app_src.parent / name if (app_src.parent / name).exists() else app_src / name
        if src.exists():
            dst = INSTALL_DIR / name
            if dst.exists():
                dst.unlink()
            shutil.copy2(src, dst)
            print("Copied", name, "to", dst)

    # copy systemd directory if present under extracted tree
    src_systemd = app_src.parent / "systemd"
    if src_systemd.exists():
        dest_systemd = INSTALL_DIR / "systemd"
        if dest_systemd.exists():
            shutil.rmtree(dest_systemd)
        shutil.copytree(src_systemd, dest_systemd)
        print("Copied systemd directory to", dest_systemd)


def ensure_init_files():
    """Make sure python package imports work."""
    pkg_paths = [
        INSTALL_DIR / "robot_server",
        INSTALL_DIR / "robot_server" / "routers",
        INSTALL_DIR / "robot_server" / "services",
    ]
    for p in pkg_paths:
        p.mkdir(parents=True, exist_ok=True)
        init = p / "__init__.py"
        if not init.exists():
            init.touch()
            print("Created", init)


def install_requirements(pip_bin):
    req = INSTALL_DIR / "requirements.txt"
    if not req.exists():
        print("No requirements.txt, skipping pip install")
        return
    print("Installing requirements from", req)
    rc, out, err = run_cmd([pip_bin, "install", "-r", str(req)], check=False)
    if rc != 0:
        print("⚠️ pip install returned non-zero. Inspect stdout/stderr above.")
        # continue — user can fix OS packages then re-run `pip install -r requirements.txt` manually


def run_setup_wifi(python_bin):
    setup_script = INSTALL_DIR / "setup_wifi.py"
    if not setup_script.exists():
        print("No setup_wifi.py found, skipping")
        return
    print("Running setup_wifi.py (sudo, best-effort)")
    run_cmd([python_bin, str(setup_script)], sudo=True, check=False)


def install_existing_systemd_from_repo(venv_python):
    """
    Take existing service file at INSTALL_DIR/systemd/lars-robot-server.service,
    patch it (WorkingDirectory + PYTHONPATH + ExecStart -> use venv_python),
    write to /etc/systemd/system/lars-robot-server.service (overwrite),
    daemon-reload, enable & start.
    """
    repo_service = INSTALL_DIR / "systemd" / "lars-robot-server.service"
    if not repo_service.exists():
        print("❌ service file not found at", repo_service)
        print("Looked in", repo_service.parent)
        return False

    print("Reading service file from", repo_service)
    txt = repo_service.read_text()

    # Replace WorkingDirectory line (if present), else insert under [Service]
    if re.search(r'(?m)^WorkingDirectory=', txt):
        txt = re.sub(r'(?m)^WorkingDirectory=.*$', f"WorkingDirectory={INSTALL_DIR}", txt)
    else:
        # insert after [Service]
        txt = re.sub(r'(?m)^\[Service\]\s*', f"[Service]\nWorkingDirectory={INSTALL_DIR}\n", txt, count=1)

    # Replace or add PYTHONPATH env
    if re.search(r'(?m)^Environment=PYTHONPATH=', txt):
        txt = re.sub(r'(?m)^Environment=PYTHONPATH=.*$', f"Environment=PYTHONPATH={INSTALL_DIR}", txt)
    else:
        # add after WorkingDirectory
        txt = re.sub(r'(?m)^(WorkingDirectory=.*)$', r"\1\nEnvironment=PYTHONPATH=" + str(INSTALL_DIR), txt, count=1)

    # Replace ExecStart to use venv python explicitly
    # We produce a deterministic ExecStart that invokes venv python -m uvicorn robot_server.main:app
    new_exec = f"ExecStart={venv_python} -m uvicorn robot_server.main:app --host 0.0.0.0 --port 8081"
    if re.search(r'(?m)^ExecStart=', txt):
        txt = re.sub(r'(?m)^ExecStart=.*$', new_exec, txt, count=1)
    else:
        # if no ExecStart present (unlikely), append it under [Service]
        txt = re.sub(r'(?m)^\[Service\]\s*', f"[Service]\n{new_exec}\n", txt, count=1)

    # Write temp and copy to /etc/systemd/system
    tmp = Path("/tmp/lars-robot-server.service")
    tmp.write_text(txt)
    print("Writing patched unit to", SYSTEMD_TARGET, "(overwriting if exists)")

    # remove existing target if present, then copy
    if SYSTEMD_TARGET.exists():
        run_cmd(["sudo", "rm", "-f", str(SYSTEMD_TARGET)])

    rc, out, err = run_cmd(["sudo", "cp", str(tmp), str(SYSTEMD_TARGET)], check=False)
    if rc != 0:
        print("❌ failed to copy unit file to", SYSTEMD_TARGET)
        return False

    run_cmd(["sudo", "systemctl", "daemon-reload"])
    run_cmd(["sudo", "systemctl", "enable", "lars-robot-server.service"])
    run_cmd(["sudo", "systemctl", "restart", "lars-robot-server.service"], check=False)
    run_cmd(["sudo", "systemctl", "status", "lars-robot-server"], check=False)
    return True


def main():
    print("=== LARS Robot Server installer (using repo's existing systemd unit) ===")

    # 1) stop existing (best-effort)
    run_cmd(["sudo", "systemctl", "stop", "lars-robot-server"], check=False)

    # 2) remove existing app files
    for item in ["robot_server", "requirements.txt", "setup_wifi.py", "systemd", "VERSION"]:
        p = INSTALL_DIR / item
        if p.exists():
            if p.is_dir():
                print("Removing directory", p)
                shutil.rmtree(p)
            else:
                print("Removing file", p)
                p.unlink()

    # 3) download + extract
    tmp_dir, app_src = download_and_extract()

    # 4) copy application files
    copy_app_files(app_src)

    # 5) ensure package init files for imports
    ensure_init_files()

    # 6) create venv
    python_choice = find_python_prefer_311()
    venv_python, venv_pip = create_venv(python_choice)

    # 7) install requirements
    install_requirements(venv_pip)

    # 8) run setup_wifi.py (optional)
    run_setup_wifi(venv_python)

    # 9) install/patch existing service from repo/systemd
    ok = install_existing_systemd_from_repo(venv_python)
    if not ok:
        print("⚠️ Existing service not installed. Check that", INSTALL_DIR / "systemd" / "lars-robot-server.service", "exists and try again.")

    print("\nDone. If service failed, inspect logs with:")
    print("  sudo journalctl -u lars-robot-server -b --no-pager")
    print("  sudo systemctl status lars-robot-server --no-pager")

if __name__ == "__main__":
    main()
