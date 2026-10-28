"""Local tooling report; safe to run without an API key or network access."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("streamlit", "pydantic", "openai", "python-dotenv", "pytest")


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Executable: {sys.executable}")
    print(f"Platform: {sys.platform}")
    print(f"Virtual environment: {'yes' if sys.prefix != sys.base_prefix else 'no'}")
    if sys.version_info < (3, 11):
        print("FAIL: Python 3.11+ is required.")
        return 1

    for executable in ("git", "codex", "gh"):
        path = shutil.which(executable)
        if path:
            result = subprocess.run([executable, "--version"], text=True, capture_output=True, check=False)
            output = (result.stdout or result.stderr).strip().splitlines()
            print(f"{executable}: {output[0] if output else 'installed'}")
        else:
            print(f"{executable}: not found in PATH (codex and gh are optional)")

    missing = []
    for name in PACKAGES:
        try:
            installed_version = version(name)
            print(f"{name}: {installed_version}")
        except PackageNotFoundError:
            print(f"{name}: NOT INSTALLED")
            missing.append(name)

    print(f".env exists: {(ROOT / '.env').exists()}")
    print(f"MODEL_API_KEY in process environment: {'set' if bool(os.getenv('MODEL_API_KEY')) else 'not set'}")
    if missing:
        print("Install dependencies: python -m pip install -r requirements.txt")
        return 1
    print("DOCTOR PASS: Python and dependencies are available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
