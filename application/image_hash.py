"""Image hashing helpers for capture and verification.

Computes strict SHA-256 over original image bytes and perceptual pHash from decoded
image pixels so verification can distinguish exact, modified, and unknown photos.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import imagehash
from PIL import Image, UnidentifiedImageError

PHASH_DISTANCE_THRESHOLD = 10


def read_image_data(image_data: bytes | str) -> bytes:
    """Load image bytes from raw bytes or a filesystem path.

    Args:
        image_data: Image bytes or path to an image file.

    Returns:
        Raw image bytes.

    Raises:
        TypeError: If the input type is unsupported.
    """
    if isinstance(image_data, bytes):
        return image_data
    if isinstance(image_data, str):
        return Path(image_data).read_bytes()
    raise TypeError("image_data must be bytes or a file path string")


def compute_image_hash(image_data: bytes | str) -> str:
    """Compute the strict SHA-256 hash of image bytes.

    Args:
        image_data: Image bytes or path to an image file.

    Returns:
        SHA-256 hex digest of the raw image bytes.
    """
    return hashlib.sha256(read_image_data(image_data)).hexdigest()


def compute_phash(image_data: bytes | str) -> str:
    """Compute the perceptual hash of an image.

    Args:
        image_data: Image bytes or path to an image file.

    Returns:
        ImageHash pHash encoded as a hex string.

    Raises:
        ValueError: If the image cannot be decoded.
    """
    raw_bytes = read_image_data(image_data)
    try:
        with Image.open(BytesIO(raw_bytes)) as image:
            return str(imagehash.phash(image.convert("RGB")))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("image_data is not a decodable image") from exc


def phash_distance(left: str, right: str) -> int:
    """Compute Hamming distance between two pHash strings.

    Args:
        left: First ImageHash pHash hex string.
        right: Second ImageHash pHash hex string.

    Returns:
        Integer Hamming distance.

    Raises:
        ValueError: If either pHash string is invalid.
    """
    try:
        return imagehash.hex_to_hash(left) - imagehash.hex_to_hash(right)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid pHash value") from exc
