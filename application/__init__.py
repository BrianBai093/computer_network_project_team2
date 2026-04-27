"""TrueShot application package.

Owns user-facing photo provenance workflows and exposes the stable Layer 3 API.
Application code creates, signs, verifies, and queries semantic transactions while
using blockchain Chain, Mempool, and Transaction only through public methods.
"""

from application.capture import record_capture
from application.device import register_device
from application.endorse import endorse_capture, get_endorsements
from application.models import VerifyDetail, VerifyResult
from application.verify import verify_image
from application.wallet import Wallet

__all__ = [
    "Wallet",
    "VerifyDetail",
    "VerifyResult",
    "endorse_capture",
    "get_endorsements",
    "record_capture",
    "register_device",
    "verify_image",
]
