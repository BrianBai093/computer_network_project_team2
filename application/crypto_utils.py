"""
crypto_utils.py — ECDSA key generation, signing, and verification

Uses the ecdsa library with the NIST384p curve.

Functions:
  generate_keypair()             -> (private_key_hex, public_key_hex)
  sign(private_key_hex, data)    -> signature_hex
  verify(public_key_hex, data, signature_hex) -> bool
  pubkey_to_device_id(pubkey_hex) -> str   (first 16 bytes as hex)
"""

import hashlib

import ecdsa

from config import CURVE

_CURVE_MAP = {
    "NIST384p": ecdsa.NIST384p,
    "NIST256p": ecdsa.NIST256p,
}
_CURVE = _CURVE_MAP.get(CURVE, ecdsa.NIST384p)


def generate_keypair() -> tuple[str, str]:
    """
    Generate an ECDSA key pair.

    Returns:
        (private_key_hex, public_key_hex)
    """
    sk = ecdsa.SigningKey.generate(curve=_CURVE)
    vk = sk.get_verifying_key()
    return sk.to_string().hex(), vk.to_string().hex()


def sign(private_key_hex: str, data: bytes) -> str:
    """
    Sign data with the private key.

    Args:
        private_key_hex: Hexadecimal private key string
        data:            Bytes to sign

    Returns:
        Hexadecimal signature string
    """
    sk = ecdsa.SigningKey.from_string(
        bytes.fromhex(private_key_hex), curve=_CURVE
    )
    signature = sk.sign(data, hashfunc=hashlib.sha256)
    return signature.hex()


def verify(public_key_hex: str, data: bytes, signature_hex: str) -> bool:
    """
    Verify a signature.

    Returns:
        True if the signature is valid, False otherwise
    """
    try:
        vk = ecdsa.VerifyingKey.from_string(
            bytes.fromhex(public_key_hex), curve=_CURVE
        )
        vk.verify(bytes.fromhex(signature_hex), data, hashfunc=hashlib.sha256)
        return True
    except ecdsa.BadSignatureError:
        return False
    except Exception:
        return False


def pubkey_to_device_id(pubkey_hex: str) -> str:
    """
    Derive a device ID from the public key hash
    (first 16 bytes of SHA-256 as hex, 32 characters).
    """
    digest = hashlib.sha256(bytes.fromhex(pubkey_hex)).hexdigest()
    return digest[:32]
