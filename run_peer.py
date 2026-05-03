#!/usr/bin/env python3
"""
run_peer.py — Start a Peer node

Usage:
  python run_peer.py --tracker-url http://localhost:5000 --web-port 8001

Options:
  --tracker-url   Tracker server address (required)
  --web-port      Web/API port for this node (default 8001)
  --wallet-file   Path to wallet file (default wallet.json)
  --no-mine       Disable the background mining thread
"""

import argparse
import logging
import signal
import sys
import threading

from config import PEER_DEFAULT_PORT, WALLET_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PEER] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def build_node_state(wallet_file: str) -> dict:
    """Initialize the shared node state dictionary."""
    from blockchain.chain import Chain
    from blockchain.mempool import Mempool
    from network.gossip import SeenMessages
    from application.wallet import Wallet

    return {
        "chain": Chain(),
        "mempool": Mempool(),
        "known_peers": set(),
        "seen": SeenMessages(),
        "wallet": Wallet.from_file(wallet_file),
        "stop_event": threading.Event(),
        "self_url": "",   # filled after registration
    }


def install_signal_handlers(stop_event: threading.Event) -> None:
    """Wire Ctrl-C and termination signals to the shared stop event.

    Args:
        stop_event: Event used by background threads for graceful shutdown.
    """
    def handle_shutdown(signum, frame):
        log.info("Shutdown signal received; stopping background threads")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)


def start_mining(state: dict, difficulty: int):
    """
    Background mining thread: continuously pull transactions from the mempool,
    mine a new block, append it to the chain, and broadcast it.
    """
    from blockchain.mining import mine_block, adjust_difficulty
    from network.peer_client import broadcast_block

    chain = state["chain"]
    mempool = state["mempool"]
    wallet = state["wallet"]
    stop = state["stop_event"]

    log.info("Mining thread started (difficulty %d)", difficulty)

    while not stop.is_set():
        txs  = mempool.get_pending()
        if not txs:
            stop.wait(1)
            continue
        prev = chain.last_block
        blk = mine_block(prev, txs, wallet.public_key,
                         difficulty, stop_event=stop)
        if blk is None:
            break   # stop_event triggered

        appended = chain.append_block(blk, difficulty=difficulty)
        if not appended:
            log.warning("Block #%d failed validation (difficulty=%d, hash=%s…)",
                        blk.index, difficulty, blk.hash[:16])
        if appended:
            mempool.remove([tx.tx_id for tx in txs])
            log.info("New block #%d mined, hash %s...", blk.index, blk.hash[:16])
            import event_bus
            event_bus.emit("block_mined",
                index=blk.index,
                hash=blk.hash[:16],
                tx_count=len(blk.transactions),
                height=chain.height,
            )
            broadcast_block(blk, list(state["known_peers"]),
                            exclude_self=state.get("self_url", ""))

            # Dynamic difficulty adjustment — exclude genesis (timestamp=0)
            # to avoid the enormous interval distorting the average.
            all_blocks = chain.get_all_blocks()
            real_blocks = [b for b in all_blocks if b.timestamp > 0.0]
            if len(real_blocks) >= 2:
                timestamps = [b.timestamp for b in real_blocks[-10:]]
                difficulty = adjust_difficulty(timestamps,
                                               current_difficulty=difficulty)


def main():
    parser = argparse.ArgumentParser(description="TrueShot Peer Node")
    parser.add_argument("--tracker-url", required=True,
                        help="Tracker server address, e.g. http://localhost:5000")
    parser.add_argument("--web-port", type=int, default=PEER_DEFAULT_PORT,
                        help=f"Listening port for this node (default {PEER_DEFAULT_PORT})")
    parser.add_argument("--wallet-file", default=WALLET_FILE,
                        help=f"Path to wallet file (default {WALLET_FILE})")
    parser.add_argument("--no-mine", action="store_true",
                        help="Disable background mining")
    args = parser.parse_args()

    self_url = f"http://127.0.0.1:{args.web_port}"

    # ── Initialize state ─────────────────────────────────
    state = build_node_state(args.wallet_file)
    state["self_url"] = self_url
    install_signal_handlers(state["stop_event"])

    # ── Register with Tracker + initial sync ─────────────
    from network.peer_client import register_with_tracker
    from network.sync import initial_sync, heartbeat_loop

    ok = register_with_tracker(args.tracker_url, self_url)
    log.info("Tracker registration: %s", "OK" if ok else "FAILED (tracker may not be running)")

    initial_sync(state, args.tracker_url)
    log.info("Initial sync complete, chain height %d", state["chain"].height)

    # ── Heartbeat background thread ───────────────────────
    hb_thread = threading.Thread(
        target=heartbeat_loop,
        args=(state, args.tracker_url, self_url),
        daemon=True,
    )
    hb_thread.start()

    # ── Mining background thread ──────────────────────────
    if not args.no_mine:
        from config import DIFFICULTY_BITS
        mine_thread = threading.Thread(
            target=start_mining,
            args=(state, DIFFICULTY_BITS),
            daemon=True,
        )
        mine_thread.start()

    # ── Start Flask ───────────────────────────────────────
    from web.app import create_app
    app = create_app(state)

    log.info("Peer node running at %s", self_url)
    app.run(host="0.0.0.0", port=args.web_port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
