"""Desktop client launcher — wraps the web UI in a native window using pywebview."""

import sys
import threading
import time
from pathlib import Path

import uvicorn
import webview


def find_free_port(start=8000) -> int:
    """Find a free port starting from `start`."""
    import socket
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


class ServerThread(threading.Thread):
    """Runs the FastAPI server in a background thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self._ready = threading.Event()

    def run(self):
        config = uvicorn.Config(
            "src.web_server:app",
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        # Signal ready after server starts
        def on_startup():
            self._ready.set()

        server.started = on_startup
        server.run()

    def wait_ready(self, timeout: float = 10.0):
        return self._ready.wait(timeout)


def main():
    port = find_free_port()
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    print(f"Starting server on {url} ...")
    server = ServerThread(host=host, port=port)
    server.start()

    if not server.wait_ready(timeout=5.0):
        print("Server failed to start within 5 seconds.")
        sys.exit(1)

    print(f"Server ready. Opening desktop window...")

    webview.create_window(
        title="需求到代码 Agent",
        url=url,
        width=1400,
        height=900,
        min_size=(1024, 680),
        resizable=True,
        fullscreen=False,
        text_select=True,
    )

    # webview.start() blocks until the window is closed
    webview.start()
    print("Window closed. Exiting.")


if __name__ == "__main__":
    main()
