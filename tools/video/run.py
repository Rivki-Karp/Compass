"""Runs the demo video against the LIVE site. Started by `tasks.py record-video [--dry-run]`.

    --cleanup-admin   lists admin@demo.compass's own conversations (left by earlier dry runs) and
                      deletes them after you type "yes"; nothing else is touched
    --dry-run   no recording: every scene runs once; prints PASS / FAIL per scene
    (none)      records (at most 3 takes), then edits the first cut (edit.py)

The three passwords come from COMPASS_VIDEO_EMPLOYEE_PASSWORD / _REP_ / _ADMIN_; any that is
missing is asked for with hidden input (getpass). They live in this process and in the child's
environment only: never printed, saved or logged. Nothing here touches the product.
"""

import os
import shutil
import subprocess
import sys
from getpass import getpass
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
ROLES = ("employee", "rep", "admin")
MAX_TAKES = 3


def passwords() -> dict[str, str]:
    env = {}
    for role in ROLES:
        name = f"COMPASS_VIDEO_{role.upper()}_PASSWORD"
        value = os.environ.get(name, "")
        if not value:
            value = getpass(f"{role} password (hidden, kept in memory only): ")
        if not value:
            sys.exit(f"record-video: no {role} password")
        env[name] = value
    return env


def node_run(args: list[str], env: dict[str, str]) -> int:
    node = shutil.which("node")
    if node is None:
        sys.exit("record-video: node is not on PATH")
    child_env = {**os.environ, **env}
    return subprocess.run([node, str(HERE / "record.mjs"), *args], env=child_env).returncode


def cleanup_admin() -> int:
    """List the admin's own conversations, then delete them on an explicit "yes". The password is
    asked for (hidden) unless it is in the environment; it is never printed."""
    import json
    import urllib.request

    api = os.environ.get("COMPASS_VIDEO_API", "https://compass-api-tft8.onrender.com").rstrip("/")
    password = os.environ.get("COMPASS_VIDEO_ADMIN_PASSWORD") or getpass("admin password (hidden): ")

    def call(method: str, route: str, token: str | None = None, body: dict | None = None):
        headers = {"content-type": "application/json"} if body else {}
        if token:
            headers["authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body else None
        request = urllib.request.Request(f"{api}/api{route}", data=data, method=method, headers=headers)
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    token = call("POST", "/auth/login", body={"email": "admin@demo.compass", "password": password})["token"]
    rows = call("GET", "/conversations", token) or []
    if not rows:
        print("admin@demo.compass has no conversations; nothing to delete")
        return 0
    print(f"admin@demo.compass's conversations ({len(rows)}):")
    for row in rows:
        print(f"  {row['id']}  {row['updated_at']}  [{row['status']}]  {row['title']}")
    if input('Type "yes" to delete exactly these: ').strip() != "yes":
        print("nothing deleted")
        return 1
    for row in rows:
        call("DELETE", f"/conversations/{row['id']}", token)
        print(f"deleted {row['id']}")
    return 0


def main(args: list[str]) -> int:
    if args == ["--cleanup-admin"]:
        return cleanup_admin()
    if any(a not in ("--dry-run",) for a in args):
        sys.exit("record-video: the options are --dry-run and --cleanup-admin")
    dry = "--dry-run" in args
    sys.path.insert(0, str(HERE))
    import edit  # the ffmpeg side: checked BEFORE a live recording is spent

    if not dry:
        edit.find_tool("ffmpeg")  # exits with the install hint when it is missing
    env = passwords()
    if dry:
        return node_run(["--mode", "dry"], env)

    for take in range(1, MAX_TAKES + 1):
        print(f"\n=== take {take} of at most {MAX_TAKES} ===", flush=True)
        shutil.rmtree(OUT / "raw", ignore_errors=True)
        code = node_run(["--mode", "record"], env)
        if code == 0:
            break
        print(f"take {take} did not pass every scene (exit {code})", flush=True)
        if code == 2:  # a precondition or an error, not a scene: another take will not help
            return code
    else:
        print("record-video: no take passed; nothing was edited", flush=True)
        return 1
    return edit.main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
