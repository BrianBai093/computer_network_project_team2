#!/usr/bin/env python3
"""
Attack 3: Photo Tampering Detection Bypass

Tests whether the system can detect AI-tampered photos. This attack:

  1. Takes an original photo that was registered on the blockchain
  2. Applies various modifications (resize, compress, pixel edits, metadata strip)
  3. Submits each variant to the /verify endpoint
  4. Reports which modifications evade detection

Exploits:
  - pHash with threshold=10 allows significant visual changes to pass as "similar"
  - SHA-256 exact match is all-or-nothing: even 1 bit change makes it UNKNOWN
  - There is a gap: modifications that change SHA-256 but keep pHash close are
    flagged as SUSPICIOUS rather than rejected

This demonstrates the fundamental limitation: the system can detect exact copies
and near-duplicates, but sophisticated AI modifications (style transfer, object
removal, face swap) that preserve overall structure may still pass pHash check.
"""

import argparse
import io
import os
import sys

import requests
from PIL import Image, ImageFilter, ImageEnhance

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def load_image(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def apply_modifications(img: Image.Image) -> list[tuple[str, bytes]]:
    """Apply various modifications and return (name, bytes) pairs."""
    variants = []

    # 0. Original (control)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    variants.append(("original", buf.getvalue()))

    # 1. Re-encode at different quality (changes SHA-256, pHash stays same)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50)
    variants.append(("jpeg_q50", buf.getvalue()))

    # 2. Slight resize (99% size)
    w, h = img.size
    resized = img.resize((int(w * 0.99), int(h * 0.99)), Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="JPEG", quality=95)
    variants.append(("resize_99pct", buf.getvalue()))

    # 3. Slight crop (1% from each edge)
    crop_box = (int(w * 0.01), int(h * 0.01), int(w * 0.99), int(h * 0.99))
    cropped = img.crop(crop_box)
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=95)
    variants.append(("crop_1pct", buf.getvalue()))

    # 4. Gaussian blur
    blurred = img.filter(ImageFilter.GaussianBlur(radius=2))
    buf = io.BytesIO()
    blurred.save(buf, format="JPEG", quality=95)
    variants.append(("blur_r2", buf.getvalue()))

    # 5. Brightness adjustment
    enhancer = ImageEnhance.Brightness(img)
    bright = enhancer.enhance(1.1)
    buf = io.BytesIO()
    bright.save(buf, format="JPEG", quality=95)
    variants.append(("brightness_110pct", buf.getvalue()))

    # 6. Contrast adjustment
    enhancer = ImageEnhance.Contrast(img)
    contrast = enhancer.enhance(1.2)
    buf = io.BytesIO()
    contrast.save(buf, format="JPEG", quality=95)
    variants.append(("contrast_120pct", buf.getvalue()))

    # 7. Horizontal flip (significant visual change but structure preserved)
    flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
    buf = io.BytesIO()
    flipped.save(buf, format="JPEG", quality=95)
    variants.append(("horizontal_flip", buf.getvalue()))

    # 8. Add noise (simulate pixel-level tampering)
    import random
    noisy = img.copy()
    pixels = noisy.load()
    for x in range(0, w, 10):
        for y in range(0, h, 10):
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                min(255, max(0, r + random.randint(-20, 20))),
                min(255, max(0, g + random.randint(-20, 20))),
                min(255, max(0, b + random.randint(-20, 20))),
            )
    buf = io.BytesIO()
    noisy.save(buf, format="JPEG", quality=95)
    variants.append(("sparse_noise", buf.getvalue()))

    # 9. Color shift (simulate color correction AI tool)
    shifted = ImageEnhance.Color(img).enhance(0.5)
    buf = io.BytesIO()
    shifted.save(buf, format="JPEG", quality=95)
    variants.append(("desaturate_50pct", buf.getvalue()))

    # 10. Heavy crop (25% - should break pHash)
    heavy_crop = img.crop((int(w * 0.25), int(h * 0.25), int(w * 0.75), int(h * 0.75)))
    buf = io.BytesIO()
    heavy_crop.save(buf, format="JPEG", quality=95)
    variants.append(("heavy_crop_25pct", buf.getvalue()))

    # 11. Format change to PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    variants.append(("format_png", buf.getvalue()))

    return variants


def verify_image(target_url: str, image_bytes: bytes) -> dict:
    """Submit an image to the victim's /verify endpoint and parse the result."""
    files = {"image": ("test.jpg", image_bytes, "image/jpeg")}
    try:
        resp = requests.post(f"{target_url}/verify", files=files, timeout=10, allow_redirects=False)
        if resp.status_code == 302:
            return {"result": "ERROR", "note": "redirected (possibly flash error)"}
        return {"result": "OK", "status_code": resp.status_code, "body_length": len(resp.text)}
    except Exception as e:
        return {"result": "ERROR", "error": str(e)}


def verify_via_api(target_url: str, image_bytes: bytes) -> dict | None:
    """Try to verify via the web form and parse HTML for result."""
    files = {"image": ("test.jpg", image_bytes, "image/jpeg")}
    try:
        resp = requests.post(f"{target_url}/verify", files=files, timeout=10)
        text = resp.text.lower()
        if "authentic" in text:
            return {"result": "AUTHENTIC"}
        elif "suspicious" in text:
            return {"result": "SUSPICIOUS"}
        elif "unknown" in text or "no matching" in text:
            return {"result": "UNKNOWN"}
        else:
            return {"result": "PARSE_FAILED", "status": resp.status_code}
    except Exception as e:
        return {"result": "ERROR", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Attack 3: Photo tampering test")
    parser.add_argument("--target", required=True, help="Victim peer URL")
    parser.add_argument("--image", required=True, help="Path to original photo (should be registered on chain)")
    args = parser.parse_args()

    print(f"[*] Loading image from {args.image}...")
    img = load_image(args.image)
    print(f"[*] Image size: {img.size}")

    print(f"[*] Generating {12} modified variants...")
    variants = apply_modifications(img)

    print(f"\n{'Variant':<25} {'Result':<15} {'Details'}")
    print("-" * 70)

    for name, data in variants:
        result = verify_via_api(args.target, data)
        status = result.get("result", "?")
        details = {k: v for k, v in result.items() if k != "result"}
        marker = ""
        if status == "AUTHENTIC":
            marker = " <-- BYPASS!"
        elif status == "UNKNOWN":
            marker = " <-- EVADED DETECTION"
        print(f"{name:<25} {status:<15} {details}{marker}")

    print("\n[*] Analysis complete.")
    print("[*] AUTHENTIC = system thinks it's the original (bypass if this is a modified version)")
    print("[*] SUSPICIOUS = system detected similarity but bytes differ (partial detection)")
    print("[*] UNKNOWN = system has no record (complete evasion of provenance tracking)")


if __name__ == "__main__":
    main()
