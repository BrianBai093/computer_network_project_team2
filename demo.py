#!/usr/bin/env python3
"""Small TrueShot demo launcher for Member D.

This script starts one tracker and three peer nodes. It is intentionally light
because the exact UI workflow still depends on the current web forms/templates.
Run it from the project root:

    python demo.py
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
TRACKER_PORT = 50000
TRACKER_URL = f"http://127.0.0.1:{TRACKER_PORT}"
PEER_PORTS = [8001, 8002, 8003]
WALLETS_DIR = ROOT / "wallets"
DEMO_PORTS = [TRACKER_PORT, *PEER_PORTS]


def start_process(command: list[str]) -> subprocess.Popen:
    """Start a subprocess from the project root."""
    print("Starting:", " ".join(command))
    return subprocess.Popen(command, cwd=ROOT)


def _listening_pids(port: int) -> set[int]:
    """Return PIDs currently listening on a TCP port."""
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return set()

    pids: set[int] = set()
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid != os.getpid():
            pids.add(pid)
    return pids


def free_demo_ports() -> None:
    """Stop old demo processes that still occupy the configured demo ports."""
    pids: set[int] = set()
    for port in DEMO_PORTS:
        pids.update(_listening_pids(port))

    if not pids:
        return

    print("Stopping existing processes on demo ports:", ", ".join(map(str, sorted(pids))))
    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    deadline = time.time() + 5
    while time.time() < deadline:
        if not any(_listening_pids(port) for port in DEMO_PORTS):
            return
        time.sleep(0.2)

    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


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
    WALLETS_DIR.mkdir(exist_ok=True)
    free_demo_ports()
    try:
        processes.append(start_process([sys.executable, "run_tracker.py", "--port", str(TRACKER_PORT)]))
        if wait_for_health(f"{TRACKER_URL}/health"):
            print("Tracker is healthy")
        else:
            print("Tracker did not become healthy in time")

        for port in PEER_PORTS:
            processes.append(start_process([
                sys.executable, "run_peer.py",
                "--tracker-url", TRACKER_URL,
                "--web-port", str(port),
                "--wallet-file", str(WALLETS_DIR / f"peer-{port}.json"),
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
