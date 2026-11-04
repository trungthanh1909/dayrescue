"""Local-only launcher: python -m api. Live generation stays process-gated."""
from importlib.util import find_spec
import sys


def main():
    if any(find_spec(package) is None for package in ('uvicorn', 'fastapi')):
        print('Planning service could not start: API dependencies are missing.\n'
              'From the project folder run:\n'
              '.\\.venv\\Scripts\\python.exe -m pip install -r requirements-api.txt', file=sys.stderr)
        return 1
    import uvicorn
    try:
        uvicorn.run("api.app:app", host="127.0.0.1", port=8001, proxy_headers=False,
                    access_log=False, log_level="warning")
    except (ImportError, OSError, SystemExit):
        print('Planning service did not start. Check that port 8001 is free and API dependencies are installed.\n'
              'Do not stop an unrelated process. See web/README.md for local setup.', file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
