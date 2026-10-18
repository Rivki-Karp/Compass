"""scripts/check_image_secrets.py finds what it must (on synthetic image tars; no Docker)."""

import io
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_image_secrets import is_env_file, scan  # noqa: E402

FAKE_KEY = ("sk-" + "ant-" + "api03-" + "A1b2_C3d4-" * 4).encode()  # built, never a literal


def _tar(tmp_path: Path, files: dict[str, bytes]) -> Path:
    path = tmp_path / "image.tar"
    with tarfile.open(path, "w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def test_a_clean_image_passes(tmp_path: Path) -> None:
    clean = {"app/.env.example": b"ANTHROPIC_API_KEY=\n", "app/compass/x.py": b"print(1)\n"}
    assert scan(_tar(tmp_path, clean), key=None) == []


def test_env_files_are_found(tmp_path: Path) -> None:
    files = {"app/.env": b"X=1\n", "app/web/.env.local": b"", "app/.env.example": b""}
    problems = scan(_tar(tmp_path, files), key=None)
    assert problems == [
        "app/.env: an .env file is in the image",
        "app/web/.env.local: an .env file is in the image",
    ]


def test_a_key_pattern_is_found_without_printing_it(tmp_path: Path) -> None:
    problems = scan(_tar(tmp_path, {"app/data/x.db": b"..." + FAKE_KEY + b"..."}), key=None)
    assert problems == ["app/data/x.db: contains an Anthropic key pattern"]
    assert FAKE_KEY.decode() not in " ".join(problems)


def test_this_machines_key_is_found_in_any_shape(tmp_path: Path) -> None:
    key = b"not-shaped-like-a-key-0123456789"
    problems = scan(_tar(tmp_path, {"app/settings.json": b'{"k": "' + key + b'"}'}), key=key)
    assert problems == ["app/settings.json: contains this machine's ANTHROPIC_API_KEY"]


def test_env_file_names() -> None:
    assert is_env_file(".env") and is_env_file("a/b/.env.production")
    assert not is_env_file(".env.example") and not is_env_file("app/environment.py")
