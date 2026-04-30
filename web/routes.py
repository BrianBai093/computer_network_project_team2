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
"""

from datetime import datetime
import math

from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, current_app)

web_bp = Blueprint("web", __name__)
BLOCKS_PER_PAGE = 10


def _state():
    return current_app.config["NODE_STATE"]


def _format_timestamp(timestamp: float) -> str:
    """Convert a Unix timestamp into a readable local datetime string.

    Args:
        timestamp: Unix timestamp as a float.

    Returns:
        A readable datetime string. If formatting fails, returns the raw value
        as a string so the explorer page does not crash.
    """
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(timestamp)


def _block_to_view(block):
    """Build a template-friendly block dictionary.

    Args:
        block: Block object from the blockchain layer.

    Returns:
        Dictionary containing original block fields plus timestamp_display.
    """
    if hasattr(block, "to_dict"):
        data = block.to_dict()
    else:
        data = dict(block)
    data["timestamp_display"] = _format_timestamp(data.get("timestamp"))
    return data


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
        metadata = {
            "model": request.form.get("model", ""),
            "serial": request.form.get("serial", ""),
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
        file = request.files.get("image")
        location = request.form.get("location", "")
        if not file:
            flash("Please select an image file.", "warning")
            return redirect(url_for("web.capture"))
        try:
            from application.capture import record_capture
            tx = record_capture(state["wallet"], file.read(), state["mempool"], location)
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
    if request.method == "POST":
        file = request.files.get("image")
        if not file:
            flash("Please select an image file.", "warning")
            return redirect(url_for("web.verify"))
        try:
            from application.verify import verify_image
            detail = verify_image(file.read(), state["chain"])
        except Exception as e:
            flash(f"Verification failed: {e}", "danger")

    return render_template("verify.html", detail=detail)


# ── Endorsement ───────────────────────────────────────────

@web_bp.route("/endorse", methods=["GET", "POST"])
def endorse():
    state = _state()
    if request.method == "POST":
        target_tx_id = request.form.get("target_tx_id", "").strip()
        if not target_tx_id:
            flash("Please enter a target transaction ID.", "warning")
            return redirect(url_for("web.endorse"))
        try:
            from application.endorse import endorse_capture
            tx = endorse_capture(state["wallet"], target_tx_id, state["mempool"])
            flash(f"Endorsement submitted. TX ID: {tx.tx_id[:16]}...", "success")
        except Exception as e:
            flash(f"Endorsement failed: {e}", "danger")
        return redirect(url_for("web.endorse"))

    return render_template("endorse.html")


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
