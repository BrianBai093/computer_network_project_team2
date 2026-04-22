"""
image_utils.py — Image hashing utilities

Functions:
  sha256_file(path)         -> hex str   (exact hash, tamper-detection)
  sha256_bytes(data)        -> hex str
  phash_file(path)          -> hex str   (perceptual hash, content similarity)
  phash_bytes(data)         -> hex str
  phash_distance(h1, h2)   -> int        (Hamming distance)
  is_similar(h1, h2)        -> bool      (distance <= PHASH_THRESHOLD)
"""

import hashlib
import io

from config import PHASH_THRESHOLD

try:
    from PIL import Image
    import imagehash
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def sha256_file(path: str) -> str:
    """Compute SHA-256 of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 of a byte string."""
    return hashlib.sha256(data).hexdigest()


def phash_file(path: str) -> str:
    """
    Compute the perceptual hash (pHash) of an image file on disk.
    Requires Pillow + imagehash.
    """
    if not _PIL_AVAILABLE:
        raise RuntimeError("Pillow / imagehash is not installed; cannot compute pHash")
    img = Image.open(path)
    return str(imagehash.phash(img))


def phash_bytes(data: bytes) -> str:
    """Compute the perceptual hash of image bytes."""
    if not _PIL_AVAILABLE:
        raise RuntimeError("Pillow / imagehash is not installed; cannot compute pHash")
    img = Image.open(io.BytesIO(data))
    return str(imagehash.phash(img))


def phash_distance(h1: str, h2: str) -> int:
    """
    Compute the Hamming distance between two pHash values.

    Args:
        h1, h2: Hexadecimal strings returned by phash_file / phash_bytes

    Returns:
        Hamming distance (integer)
    """
    if not _PIL_AVAILABLE:
        raise RuntimeError("Pillow / imagehash is not installed")
    ph1 = imagehash.hex_to_hash(h1)
    ph2 = imagehash.hex_to_hash(h2)
    return ph1 - ph2


def is_similar(h1: str, h2: str, threshold: int = PHASH_THRESHOLD) -> bool:
    """Return True when the Hamming distance is <= threshold (images are considered similar)."""
    return phash_distance(h1, h2) <= threshold
