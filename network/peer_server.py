"""
peer_server.py — Peer node Gossip API (Flask Blueprint)

Endpoints:
  GET  /api/blocks          Return the full chain (JSON)
  GET  /api/peers           Return the list of peers known to this node
  POST /api/block           Receive a broadcast new block
  POST /api/transaction     Receive a broadcast new transaction
  GET  /api/health          Health check
"""

import hashlib
import json

from flask import Blueprint, request, jsonify, current_app

from config import GOSSIP_TTL

peer_api = Blueprint("peer_api", __name__)


def _node_state():
    """Retrieve shared state from the Flask app context (injected by run_peer.py)."""
    return current_app.config["NODE_STATE"]


# ── Routes ────────────────────────────────────────────────────────────────────

@peer_api.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@peer_api.route("/api/blocks", methods=["GET"])
def get_blocks():
    state = _node_state()
    return jsonify({"chain": state["chain"].to_list()}), 200


@peer_api.route("/api/peers", methods=["GET"])
def get_peers():
    state = _node_state()
    return jsonify({"peers": list(state["known_peers"])}), 200


@peer_api.route("/api/transaction", methods=["POST"])
def receive_transaction():
    """
    Receive a broadcast transaction, add it to the mempool, and continue forwarding (Gossip).
    body: {tx: <Transaction dict>, ttl: int, msg_id: str}
    """
    data   = request.get_json(silent=True) or {}
    msg_id = data.get("msg_id", "")
    ttl    = int(data.get("ttl", GOSSIP_TTL))
    tx_dict = data.get("tx")

    if not tx_dict or not msg_id:
        return jsonify({"error": "invalid payload"}), 400

    state = _node_state()

    # Deduplication
    if state["seen"].seen(msg_id):
        return jsonify({"status": "duplicate"}), 200

    # Add to mempool
    from blockchain.transaction import Transaction
    try:
        tx = Transaction.from_dict(tx_dict)
        state["mempool"].add(tx)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Continue Gossip
    if ttl > 0:
        from network.peer_client import broadcast_transaction
        broadcast_transaction(
            tx, list(state["known_peers"]),
            ttl=ttl - 1, msg_id=msg_id,
            exclude_self=state.get("self_url", ""),
        )

    return jsonify({"status": "ok"}), 200


@peer_api.route("/api/block", methods=["POST"])
def receive_block():
    """
    Receive a broadcast block, validate it, append to the chain, and continue forwarding.
    body: {block: <Block dict>, ttl: int, msg_id: str}
    """
    data    = request.get_json(silent=True) or {}
    msg_id  = data.get("msg_id", "")
    ttl     = int(data.get("ttl", GOSSIP_TTL))
    blk_dict = data.get("block")

    if not blk_dict or not msg_id:
        return jsonify({"error": "invalid payload"}), 400

    state = _node_state()

    if state["seen"].seen(msg_id):
        return jsonify({"status": "duplicate"}), 200

    from blockchain.block import Block
    try:
        blk = Block.from_dict(blk_dict)
        appended = state["chain"].append_block(blk)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if appended:
        # Remove the block's transactions from the local mempool
        state["mempool"].remove([tx.tx_id for tx in blk.transactions])

        if ttl > 0:
            from network.peer_client import broadcast_block
            broadcast_block(
                blk, list(state["known_peers"]),
                ttl=ttl - 1, msg_id=msg_id,
                exclude_self=state.get("self_url", ""),
            )

    return jsonify({"status": "ok", "appended": appended}), 200
