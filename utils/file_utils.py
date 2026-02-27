"""
File handling utilities for xAI MCP server.

Provides base64 encoding for local images, media download,
and auto-naming helpers for saved files.

Author: Terry kim <goandonh@gmail.com>
Co-Author: Claudie
"""

import base64
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx


def encode_image_base64(file_path: str) -> tuple[str, str]:
    """Encode a local image file to base64.

    Args:
        file_path: Path to the image file.

    Returns:
        Tuple of (base64_string, mime_type).

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If MIME type cannot be determined.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {file_path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        raise ValueError(
            f"Cannot determine MIME type for: {file_path}. "
            "Supported formats: PNG, JPEG, WebP, GIF."
        )

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return b64, mime_type


async def download_media(
    url: str,
    output_path: str,
    timeout: float = 300.0,
) -> str:
    """Download a media file (image or video) from URL to local path.

    Args:
        url: Media download URL.
        output_path: Local file path to save.
        timeout: Download timeout in seconds.

    Returns:
        The output file path.

    Raises:
        httpx.HTTPStatusError: If download fails.
    """
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)

    return str(path)


def _generate_filename(prefix: str, ext: str = ".jpg") -> str:
    """Generate a unique filename with timestamp and short UUID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    return f"{prefix}_{timestamp}_{short_id}{ext}"


async def save_image_from_url(
    url: str,
    output_dir: str,
    prefix: str = "xai_img",
) -> str:
    """Download an image from URL and save with auto-generated filename.

    Args:
        url: Image download URL.
        output_dir: Directory to save the image.
        prefix: Filename prefix.

    Returns:
        Absolute path to the saved image.
    """
    # Determine extension from URL or default to .jpg
    ext = _guess_extension_from_url(url) or ".jpg"
    filename = _generate_filename(prefix, ext)
    output_path = str(Path(output_dir) / filename)
    return await download_media(url, output_path)


def save_image_from_base64(
    b64_data: str,
    output_dir: str,
    prefix: str = "xai_img",
    mime_type: Optional[str] = None,
) -> str:
    """Decode base64 image data and save to disk.

    Args:
        b64_data: Base64-encoded image data.
        output_dir: Directory to save the image.
        prefix: Filename prefix.
        mime_type: MIME type for extension detection.

    Returns:
        Absolute path to the saved image.
    """
    ext = ".jpg"
    if mime_type:
        ext_guess = mimetypes.guess_extension(mime_type)
        if ext_guess:
            ext = ext_guess

    filename = _generate_filename(prefix, ext)
    out_path = Path(output_dir) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64_data))

    return str(out_path)


def _guess_extension_from_url(url: str) -> Optional[str]:
    """Try to guess file extension from URL path."""
    from urllib.parse import urlparse
    path = urlparse(url).path
    if "." in path.split("/")[-1]:
        ext = "." + path.split(".")[-1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"):
            return ext
    return None
