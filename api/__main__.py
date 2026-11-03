"""Local-only launcher: python -m api. Live generation stays process-gated."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.app:app", host="127.0.0.1", port=8001, proxy_headers=False,
                access_log=False, log_level="warning")
