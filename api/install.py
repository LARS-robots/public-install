#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LARS installer: local build with docker buildx (no registry), then compose up.

- Builds image lars-api:<TAG> locally with `--load` (Windows/Linux).
- No separate BuildKit container or builder creation is used.
- Optionally writes .env (API_TAG=<TAG>) for compose.yml.
- Optionally runs `docker compose up -d`.

Usage examples:
  python scripts/install.py --tag dev --write-env
  python scripts/install.py --tag dev --no-up
  python scripts/install.py --tag dev --platform linux/amd64
"""

from __future__ import annotations
import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # project root (compose.yml here)
API_DIR = ROOT / "services" / "api"
DOCKERFILE = API_DIR / "Dockerfile"

IMAGE_NAME = "lars-api"       # company tag
DEFAULT_TAG = "dev"

def run(cmd: list[str], cwd: Path | None = None, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check, env=env)

def ensure_docker() -> None:
    try:
        run(["docker", "version"], check=True)
    except Exception as e:
        print("❌ Docker не найден или не запущен. Установи/запусти Docker Desktop (Windows) или Docker Engine (Linux).")
        raise e

def ensure_buildx_available() -> None:
    try:
        run(["docker", "buildx", "version"], check=True)
    except Exception as e:
        print("❌ Docker Buildx недоступен. Требуется Docker ≥ 20.10 (Compose v2).")
        raise e

def detect_platform_arg(user_platform: str | None) -> list[str]:
    """
    Returns ["--platform", value] or [] if native is desired.
    - Windows: default linux/amd64 (под Docker Desktop это предсказуемо)
    - Linux/macOS: native by default; override with --platform if needed
    """
    if user_platform:
        return ["--platform", user_platform]
    sys_name = platform.system().lower()
    if sys_name.startswith("win"):
        return ["--platform", "linux/amd64"]
    return []

def write_env_file(tag: str) -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        out = []
        replaced = False
        for line in lines:
            if line.startswith("API_TAG="):
                out.append(f"API_TAG={tag}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            out.append(f"API_TAG={tag}")
        content = "\n".join(out) + "\n"
    else:
        content = f"API_TAG={tag}\n"
    env_path.write_text(content, encoding="utf-8")
    print(f"✔ .env обновлён: API_TAG={tag}")

def build_image(tag: str, platform_arg: list[str]) -> None:
    if not DOCKERFILE.exists():
        raise FileNotFoundError(f"Dockerfile не найден: {DOCKERFILE}")
    cmd = ["docker", "buildx", "build"]
    if platform_arg:
        cmd += platform_arg
    cmd += [
        "-f", str(DOCKERFILE),
        "-t", f"{IMAGE_NAME}:{tag}",
        "--load",
        str(API_DIR),
    ]
    run(cmd, cwd=ROOT)

def compose_up(tag: str) -> None:
    env = os.environ.copy()
    env["API_TAG"] = tag
    print(f"✳ Запуск docker compose (API_TAG={tag}, image={IMAGE_NAME}:{tag})")
    run(["docker", "compose", "up"], cwd=ROOT, env=env)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build lars-api locally with buildx and run compose (no registry).")
    p.add_argument("--tag", default=DEFAULT_TAG, help="Image tag (default: dev)")
    p.add_argument("--platform", default=None, help="linux/amd64, linux/arm64 ... (default: Windows=linux/amd64; Linux/Mac=native)")
    p.add_argument("--no-up", action="store_true", help="Only build image, do not run docker compose up")
    p.add_argument("--write-env", action="store_true", help="Write .env with API_TAG=<tag>")
    return p.parse_args()

def main() -> None:
    args = parse_args()
    ensure_docker()
    ensure_buildx_available()

    platform_arg = detect_platform_arg(args.platform)
    print(f"✳ Платформа сборки: {args.platform or (platform_arg[-1] if platform_arg else 'native')}")

    build_image(args.tag, platform_arg)

    if args.write_env:
        write_env_file(args.tag)

    if not args.no_up:
        compose_up(args.tag)

    print("✔ Готово.")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Команда завершилась ошибкой (exit={e.returncode}). См. вывод выше.")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
