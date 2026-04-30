#!/usr/bin/env python3
"""
run_tracker.py — Start the Tracker server

Usage:
  python run_tracker.py [--port PORT]

Default port: 5000
"""

import argparse
import logging

from config import TRACKER_DEFAULT_PORT
from network.tracker import create_tracker_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TRACKER] %(levelname)s %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="TrueShot Tracker Server")
    parser.add_argument("--port", type=int, default=TRACKER_DEFAULT_PORT,
                        help=f"Listening port (default {TRACKER_DEFAULT_PORT})")
    args = parser.parse_args()

    app = create_tracker_app()
    logging.info("Tracker running at http://0.0.0.0:%d", args.port)
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
