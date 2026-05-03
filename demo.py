#!/usr/bin/env python3
"""Small TrueShot demo launcher for Member D.

This script starts one tracker and three peer nodes. It is intentionally light
because the exact UI workflow still depends on the current web forms/templates.
Run it from the project root:

    python demo.py
"""

import subprocess
import sys
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
TRACKER_URL = "http://127.0.0.1:5000"
PEER_PORTS = [8001, 8002, 8003]


def start_process(command: list[str]) -> subprocess.Popen:
    """Start a subprocess from the project root."""
    print("Starting:", " ".join(command))
    return subprocess.Popen(command, cwd=ROOT)


def wait_for_health(url: str, timeout_seconds: int = 15) -> bool:
    """Poll a health endpoint until it responds or timeout expires."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            time.sleep(1)
    return False


def main() -> None:
    processes: list[subprocess.Popen] = []
    try:
        processes.append(start_process([sys.executable, "run_tracker.py", "--port", "5000"]))
        if wait_for_health(f"{TRACKER_URL}/health"):
            print("Tracker is healthy")
        else:
            print("Tracker did not become healthy in time")

        for port in PEER_PORTS:
            processes.append(start_process([
                sys.executable, "run_peer.py",
                "--tracker-url", TRACKER_URL,
                "--web-port", str(port),
            ]))
            time.sleep(1)

        for port in PEER_PORTS:
            url = f"http://127.0.0.1:{port}/api/health"
            print(f"Peer {port} health:", "OK" if wait_for_health(url) else "FAILED")

        print("\nDemo nodes are running:")
        for port in PEER_PORTS:
            print(f"  Peer UI: http://127.0.0.1:{port}")
        input("\nPress Enter to stop all demo processes...")
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("Demo stopped")


if __name__ == "__main__":
    main()
