"""Check a built image for secrets (Day 5 Stage 5). CI runs it after `docker build`.

    uv run python scripts/check_image_secrets.py compass:ci

Exports the image's filesystem (docker create + docker export) and fails when:
  - any file named .env or .env.* exists (.env.example, the template, is allowed);
  - any file contains something shaped like an Anthropic API key (sk-ant-...);
  - ANTHROPIC_API_KEY is set where this runs and its exact value is in any file.
It prints file names only, never a matched value.
"""

import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

KEY_PATTERN = re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}")
ALLOWED_ENV = {".env.example"}


def is_env_file(name: str) -> bool:
    base = PurePosixPath(name).name
    return (base == ".env" or base.startswith(".env.")) and base not in ALLOWED_ENV


def scan(tar_path: Path, key: bytes | None) -> list[str]:
    problems: list[str] = []
    with tarfile.open(tar_path) as tar:
        for member in tar:
            if is_env_file(member.name):
                problems.append(f"{member.name}: an .env file is in the image")
            if not member.isfile():
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            data = handle.read()
            if KEY_PATTERN.search(data):
                problems.append(f"{member.name}: contains an Anthropic key pattern")
            if key and key in data:
                problems.append(f"{member.name}: contains this machine's ANTHROPIC_API_KEY")
    return problems


def export(image: str, target: Path) -> None:
    container = subprocess.run(
        ["docker", "create", image], capture_output=True, text=True, check=True
    ).stdout.strip()
    try:
        subprocess.run(["docker", "export", "-o", str(target), container], check=True)
    finally:
        subprocess.run(["docker", "rm", container], capture_output=True, check=False)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    image = argv[1]
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip().encode() or None
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "image.tar"
        export(image, tar_path)
        with tarfile.open(tar_path) as tar:
            files = sum(1 for m in tar if m.isfile())
        problems = scan(tar_path, key)
    if problems:
        print(f"{image}: secrets found in the image:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    checked = "the key pattern and this machine's key" if key else "the key pattern"
    print(f"{image}: {files} files checked, no .env file, no match for {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
