"""
routes.py — Web UI routes (Flask Blueprint)

Pages:
  GET  /                    Home (chain overview)
  GET  /register            Device registration page
  POST /register            Submit registration
  GET  /capture             Photo capture page
  POST /capture             Submit capture record
  GET  /verify              Verification page
  POST /verify              Submit verification (image upload)
  GET  /endorse             Endorsement page
  POST /endorse             Submit endorsement
  GET  /explorer            Block explorer
  GET  /explorer/block/<index>  Single block detail
  GET  /uploads/<filename>  Serve locally stored capture images
"""

from datetime import datetime
import json
import math
import queue as _queue
import os

from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, current_app, send_from_directory,
                   Response, stream_with_context, g, jsonify)

web_bp = Blueprint("web", __name__)
BLOCKS_PER_PAGE = 10
UPLOAD_DIR = "uploads"


def _state():
    return current_app.config["NODE_STATE"]


def _uploads_dir() -> str:
    return os.path.join(current_app.root_path, UPLOAD_DIR)


def _format_timestamp(timestamp: float) -> str:
    """Convert a Unix timestamp into a readable local datetime string."""
    try:
        ts = float(timestamp)
        if ts == 0.0:
            return "Genesis"
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(timestamp)


def _block_to_view(block):
    """Build a template-friendly block dictionary."""
    if hasattr(block, "to_dict"):
        data = block.to_dict()
    else:
        data = dict(block)
    data["timestamp_display"] = _format_timestamp(data.get("timestamp"))
    return data


def _get_register_tx(device_id: str, chain) -> dict | None:
    """Find the first REGISTER transaction dict for a given device_id."""
    register_types = {"REGISTER", "REGISTER_DEVICE"}
    for tx in chain.get_all_transactions():
        tx_type = tx.get("tx_type") if isinstance(tx, dict) else getattr(tx, "tx_type", None)
        if tx_type not in register_types:
            continue
        payload = tx.get("payload") if isinstance(tx, dict) else getattr(tx, "payload", None)
        if isinstance(payload, dict) and payload.get("device_id") == device_id:
            if isinstance(tx, dict):
                return tx
            if hasattr(tx, "to_dict"):
                return tx.to_dict()
    return None


def _device_already_registered(device_id: str, chain, mempool) -> bool:
    """Return True if device_id already has a REGISTER tx on chain OR in mempool."""
    register_types = {"REGISTER", "REGISTER_DEVICE"}

    # Check mined blocks
    for tx in chain.get_all_transactions():
        tx_type = tx.get("tx_type") if isinstance(tx, dict) else getattr(tx, "tx_type", None)
        if tx_type not in register_types:
            continue
        payload = tx.get("payload") if isinstance(tx, dict) else getattr(tx, "payload", None)
        if isinstance(payload, dict) and payload.get("device_id") == device_id:
            return True

    # Check pending mempool
    for tx in mempool.all_transactions():
        tx_type = getattr(tx, "tx_type", None)
        payload = getattr(tx, "payload", None)
        if tx_type in register_types and isinstance(payload, dict):
            if payload.get("device_id") == device_id:
                return True

    return False


def _is_device_registered(state) -> bool:
    """Return True if this node's wallet device is registered on-chain or in mempool."""
    return _device_already_registered(
        state["wallet"].device_id, state["chain"], state["mempool"]
    )


@web_bp.before_request
def _check_registration():
    try:
        g.device_registered = _is_device_registered(_state())
    except Exception:
        g.device_registered = False


@web_bp.context_processor
def _inject_device_status():
    return {"device_registered": getattr(g, "device_registered", False)}


def _get_block_index_for_tx(tx_id: str, chain) -> int | None:
    """Return the block index that contains the transaction with the given tx_id."""
    for block in chain.get_all_blocks():
        txs = (block.get("transactions", []) if isinstance(block, dict)
               else getattr(block, "transactions", []))
        for tx in txs:
            t_id = tx.get("tx_id") if isinstance(tx, dict) else getattr(tx, "tx_id", None)
            if t_id == tx_id:
                return (block.get("index") if isinstance(block, dict)
                        else getattr(block, "index", None))
    return None


# ── Serve uploaded images ──────────────────────────────────

@web_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(_uploads_dir(), filename)


# ── Home ──────────────────────────────────────────────────

@web_bp.route("/")
def index():
    state = _state()
    chain = state["chain"]
    return render_template(
        "index.html",
        height=chain.height,
        last_hash=chain.last_block.hash,
        peer_count=len(state.get("known_peers", set())),
        mempool_size=state["mempool"].size(),
    )


# ── Device registration ───────────────────────────────────

@web_bp.route("/register", methods=["GET", "POST"])
def register():
    state = _state()
    if request.method == "POST":
        # Block duplicate registration for the same device_id
        if _device_already_registered(
            state["wallet"].device_id, state["chain"], state["mempool"]
        ):
            flash(
                "Welcome back! Your device is already active on the network.",
                "success",
            )
            return redirect(url_for("web.index"))

        metadata = {
            "device_name": request.form.get("device_name", ""),
            "serial":      request.form.get("serial", ""),
            "user_agent":  request.form.get("user_agent", ""),
        }
        try:
            from application.device import register_device
            tx = register_device(state["wallet"], state["mempool"], metadata)
            flash(f"Device registered. TX ID: {tx.tx_id[:16]}...", "success")
        except Exception as e:
            flash(f"Registration failed: {e}", "danger")
        return redirect(url_for("web.register"))

    return render_template(
        "register.html",
        device_id=state["wallet"].device_id,
        public_key=state["wallet"].public_key,
    )


# ── Photo capture ─────────────────────────────────────────

@web_bp.route("/capture", methods=["GET", "POST"])
def capture():
    state = _state()
    if request.method == "POST":
        if not g.device_registered:
            flash("Please register your device before recording a capture.", "warning")
            return redirect(url_for("web.register"))
        file = request.files.get("image")
        location = request.form.get("location", "")
        if not file:
            flash("Please select an image file.", "warning")
            return redirect(url_for("web.capture"))
        try:
            from application.capture import record_capture
            from application.image_hash import compute_image_hash
            image_data = file.read()
            original_filename = file.filename or "capture.jpg"
            tx = record_capture(
                state["wallet"], image_data, state["mempool"], location, state["chain"]
            )
            # Save original image locally as uploads/<image_hash>.<ext>
            image_hash = compute_image_hash(image_data)
            ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
            uploads = _uploads_dir()
            os.makedirs(uploads, exist_ok=True)
            dest = os.path.join(uploads, f"{image_hash}{ext}")
            if not os.path.exists(dest):
                with open(dest, "wb") as f_out:
                    f_out.write(image_data)
            # Save capture metadata (source: camera or upload)
            meta_dest = os.path.join(uploads, f"{image_hash}.meta.json")
            if not os.path.exists(meta_dest):
                capture_source = request.form.get("capture_source", "upload")
                with open(meta_dest, "w", encoding="utf-8") as mf:
                    json.dump({"capture_source": capture_source}, mf)
            flash(f"Capture recorded. TX ID: {tx.tx_id[:16]}...", "success")
        except Exception as e:
            flash(f"Capture failed: {e}", "danger")
        return redirect(url_for("web.capture"))

    return render_template("capture.html")


# ── Image verification ────────────────────────────────────

@web_bp.route("/verify", methods=["GET", "POST"])
def verify():
    state = _state()
    detail = None
    # Always pass all extra keys so templates never see UndefinedError
    extra = {
        "block_index":       None,
        "device_name":       None,
        "image_file":        None,
        "sender_display":    None,
        "timestamp_display": None,
        "capture_source":    None,
    }

    if request.method == "POST":
        file = request.files.get("image")
        if not file:
            flash("Please select an image file.", "warning")
            return redirect(url_for("web.verify"))
        try:
            from application.verify import verify_image
            detail = verify_image(file.read(), state["chain"])

            # Look up stored image for any result type
            uploads = _uploads_dir()
            if detail.image_hash:
                for ext_try in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                    if os.path.exists(os.path.join(uploads, f"{detail.image_hash}{ext_try}")):
                        extra["image_file"] = f"{detail.image_hash}{ext_try}"
                        break

            if detail.result.value == "AUTHENTIC" and detail.matched_tx_id:
                extra["block_index"] = _get_block_index_for_tx(
                    detail.matched_tx_id, state["chain"]
                )
                if detail.device_id:
                    reg_tx = _get_register_tx(detail.device_id, state["chain"])
                    if reg_tx:
                        meta = (reg_tx.get("payload") or {}).get("metadata") or {}
                        extra["device_name"] = (
                            meta.get("device_name") or meta.get("model") or "Unknown"
                        )
                if detail.capture and detail.capture.get("sender"):
                    sender = detail.capture["sender"]
                    extra["sender_display"] = f"{sender[:8]}...{sender[-4:]}"
                if detail.timestamp:
                    extra["timestamp_display"] = _format_timestamp(detail.timestamp)
                # Load capture metadata (source: camera or upload)
                meta_path = os.path.join(uploads, f"{detail.image_hash}.meta.json")
                if os.path.exists(meta_path):
                    with open(meta_path, encoding="utf-8") as mf:
                        meta = json.load(mf)
                    extra["capture_source"] = meta.get("capture_source", "upload")
        except Exception as e:
            flash(f"Verification failed: {e}", "danger")

    return render_template("verify.html", detail=detail, **extra)


# ── Endorsement ───────────────────────────────────────────

@web_bp.route("/endorse", methods=["GET", "POST"])
def endorse():
    state = _state()
    if request.method == "POST":
        if not g.device_registered:
            flash("Please register your device before endorsing.", "warning")
            return redirect(url_for("web.register"))
        target_tx_id = request.form.get("target_tx_id", "").strip()
        if not target_tx_id:
            flash("Please enter a target transaction ID.", "warning")
            return redirect(url_for("web.endorse"))
        try:
            from application.endorse import endorse_capture
            tx = endorse_capture(
                state["wallet"], target_tx_id, state["mempool"], state["chain"]
            )
            flash(f"Endorsement submitted. TX ID: {tx.tx_id[:16]}...", "success")
        except Exception as e:
            flash(f"Endorsement failed: {e}", "danger")
        return redirect(url_for("web.endorse"))

    prefill_tx_id = request.args.get("tx_id", "").strip()
    return render_template("endorse.html", prefill_tx_id=prefill_tx_id)


# ── Captures API ─────────────────────────────────────────

@web_bp.route("/api/captures")
def api_captures():
    """Return all CAPTURE transactions with image URLs and device names as JSON."""
    state = _state()
    chain = state["chain"]
    uploads = _uploads_dir()
    captures = []
    for tx in chain.get_all_transactions():
        tx_type = tx.get("tx_type") if isinstance(tx, dict) else getattr(tx, "tx_type", None)
        if tx_type != "CAPTURE":
            continue
        payload = tx.get("payload") if isinstance(tx, dict) else getattr(tx, "payload", None)
        tx_id = tx.get("tx_id") if isinstance(tx, dict) else getattr(tx, "tx_id", None)
        if not payload or not tx_id:
            continue
        device_id = payload.get("device_id")
        image_hash = payload.get("image_hash")

        image_file = None
        if image_hash:
            for ext_try in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                if os.path.exists(os.path.join(uploads, f"{image_hash}{ext_try}")):
                    image_file = f"{image_hash}{ext_try}"
                    break

        device_name = None
        if device_id:
            reg_tx = _get_register_tx(device_id, chain)
            if reg_tx:
                meta = (reg_tx.get("payload") or {}).get("metadata") or {}
                device_name = meta.get("device_name") or meta.get("model") or "Unknown"

        captures.append({
            "tx_id": tx_id,
            "device_id": device_id,
            "device_name": device_name,
            "image_hash": image_hash,
            "image_file": image_file,
            "location": payload.get("location"),
        })

    captures.reverse()  # newest first
    return jsonify(captures)


# ── Block explorer ────────────────────────────────────────

@web_bp.route("/explorer")
def explorer():
    state = _state()
    all_blocks = [_block_to_view(block) for block in state["chain"].get_all_blocks()]
    all_blocks.reverse()

    requested_page = request.args.get("page", 1, type=int)
    total_pages = max(1, math.ceil(len(all_blocks) / BLOCKS_PER_PAGE))
    page = min(max(requested_page, 1), total_pages)
    start = (page - 1) * BLOCKS_PER_PAGE
    end = start + BLOCKS_PER_PAGE

    return render_template(
        "explorer.html",
        blocks=all_blocks[start:end],
        page=page,
        total_pages=total_pages,
    )


@web_bp.route("/viz")
def visualizer():
    return render_template("viz.html")


@web_bp.route("/api/events")
def sse_events():
    """Server-Sent Events stream for the real-time visualizer."""
    import event_bus
    state = _state()

    def generate():
        q = event_bus.subscribe()
        try:
            # Send initial chain snapshot so the page renders immediately
            chain = state["chain"]
            wallet_pub = state["wallet"].public_key
            all_blks = chain.get_all_blocks()
            snapshot = {
                "type": "snapshot",
                "self_url": state.get("self_url", ""),
                "height": chain.height,
                "peer_count": len(state.get("known_peers", set())),
                "mempool_size": state["mempool"].size(),
                "peers": list(state.get("known_peers", set())),
                "blocks": [
                    {
                        "index": b.index,
                        "hash": b.hash,
                        "tx_count": len(b.transactions),
                        "ts": b.timestamp,
                        "self_mined": b.miner == wallet_pub,
                    }
                    for b in all_blks[-15:]
                ],
            }
            yield f"data: {json.dumps(snapshot)}\n\n"

            while True:
                try:
                    payload = q.get(timeout=5)
                    yield f"data: {payload}\n\n"
                except _queue.Empty:
                    # keepalive + live stats update every 5 s
                    status = {
                        "type": "status",
                        "height": state["chain"].height,
                        "peer_count": len(state.get("known_peers", set())),
                        "mempool_size": state["mempool"].size(),
                        "peers": list(state.get("known_peers", set())),
                    }
                    yield f"data: {json.dumps(status)}\n\n"
        finally:
            event_bus.unsubscribe(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@web_bp.route("/explorer/block/<int:index>")
def block_detail(index: int):
    state = _state()
    block = state["chain"].get_block(index)
    if block is None:
        flash(f"Block {index} does not exist.", "warning")
        return redirect(url_for("web.explorer"))

    all_blocks = [_block_to_view(b) for b in state["chain"].get_all_blocks()]
    all_blocks.reverse()

    return render_template(
        "explorer.html",
        blocks=all_blocks[:BLOCKS_PER_PAGE],
        selected=_block_to_view(block),
        page=1,
        total_pages=max(1, math.ceil(len(all_blocks) / BLOCKS_PER_PAGE)),
    )
