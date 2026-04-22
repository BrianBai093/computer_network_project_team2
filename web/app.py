"""
app.py — Flask application factory

create_app(node_state) -> Flask
  Registers the peer_api Blueprint (/api/*)
  Registers the web routes Blueprint (/)
  Injects node_state into app.config["NODE_STATE"]
"""

from flask import Flask

from network.peer_server import peer_api
from web.routes import web_bp


def create_app(node_state: dict) -> Flask:
    """
    Args:
        node_state: Shared runtime state dict containing chain, mempool, known_peers, etc.

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "trueshot-dev-secret"   # Development only — use a random key in production

    # Inject shared state
    app.config["NODE_STATE"] = node_state

    # Register Blueprints
    app.register_blueprint(peer_api)
    app.register_blueprint(web_bp)

    return app
