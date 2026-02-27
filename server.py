"""
Terry xAI MCP Server - Unified image and video generation.

Dedicated MCP server for xAI APIs covering:
  - Image generation (grok-imagine-image): text-to-image, image editing
  - Video generation (grok-imagine-video): text-to-video, image-to-video
  - Video editing (grok-imagine-video): restyle, add/remove objects

Designed for use with Claude Desktop, Claude Code, and OpenClaw.

Author: Terry kim <goandonh@gmail.com>
Co-Author: Claudie
"""

import json
import logging
import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from fastmcp import FastMCP

# Add package root to path for relative imports
_pkg_root = str(Path(__file__).parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from providers.xai import XaiProvider
from utils.file_utils import (
    download_media,
    encode_image_base64,
    save_image_from_base64,
    save_image_from_url,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_config_path = Path(__file__).parent / "config.yaml"
_config: dict = {}
if _config_path.exists():
    with open(_config_path) as f:
        _config = yaml.safe_load(f) or {}


def _get_config(section: str, key: str, env_var: str, default: str = "") -> str:
    """Get config value with env var override."""
    env_val = os.getenv(env_var, "")
    if env_val:
        return env_val
    cfg_val = _config.get(section, {}).get(key, "")
    if cfg_val:
        return cfg_val
    return default


_IMAGE_OUTPUT_DIR = _get_config(
    "output", "image_dir", "XAI_IMAGE_OUTPUT_DIR",
    str(Path.home() / "xai_output" / "images"),
)
_VIDEO_OUTPUT_DIR = _get_config(
    "output", "video_dir", "XAI_VIDEO_OUTPUT_DIR",
    str(Path.home() / "xai_output" / "videos"),
)

mcp = FastMCP("terry-xai")

# Lazy-initialized provider
_xai: Optional[XaiProvider] = None


def _get_xai() -> XaiProvider:
    global _xai
    if _xai is None:
        api_key = _get_config("xai", "api_key", "XAI_API_KEY")
        _xai = XaiProvider(api_key=api_key)
    return _xai


# ===================================================================
# IMAGE GENERATION TOOLS
# ===================================================================


@mcp.tool()
async def xai_generate_image(
    prompt: str,
    n: int = 1,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    response_format: str = "url",
    output_dir: Optional[str] = None,
) -> str:
    """Generate images from text using xAI grok-imagine-image.

    Generated images are automatically downloaded and saved to disk.
    Temporary URLs from xAI expire quickly, so images are always saved locally.

    Args:
        prompt: Text description of the desired image.
        n: Number of images to generate (1-10, default: 1).
        aspect_ratio: Image aspect ratio. Options: "1:1" (default), "16:9", "9:16",
            "4:3", "3:4", "3:2", "2:3", "2:1", "1:2", "auto".
        resolution: Output resolution (e.g., "2k"). Omit for default.
        response_format: API response format - "url" (default) or "b64_json".
            Both are saved locally regardless of format.
        output_dir: Directory to save images. Default: ~/xai_output/images.
    """
    result = await _get_xai().generate_image(
        prompt=prompt,
        n=n,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        response_format=response_format,
    )

    # Auto-save images to disk
    save_dir = output_dir or _IMAGE_OUTPUT_DIR
    for img in result.images:
        if img.url:
            try:
                img.saved_path = await save_image_from_url(
                    url=img.url, output_dir=save_dir, prefix="xai_img",
                )
            except Exception as e:
                logger.error("Failed to download image: %s", e)
        elif img.b64_json:
            try:
                img.saved_path = save_image_from_base64(
                    b64_data=img.b64_json, output_dir=save_dir, prefix="xai_img",
                )
            except Exception as e:
                logger.error("Failed to save base64 image: %s", e)

    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def xai_edit_image(
    prompt: str,
    image_url: Optional[str] = None,
    image_local_path: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_mime_type: str = "image/jpeg",
    n: int = 1,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    response_format: str = "url",
    output_dir: Optional[str] = None,
) -> str:
    """Edit or transform an image using xAI grok-imagine-image with a reference image.

    Provide a reference image via URL, local file path, or base64 data.
    The API accepts exactly 1 reference image.

    Use cases: style transfer, image editing, multi-turn editing (chain results back).

    Args:
        prompt: Editing instruction or style description.
        image_url: Public URL of the reference image.
        image_local_path: Local file path to reference image (auto-encodes to base64 data URI).
        image_base64: Raw base64-encoded image data.
        image_mime_type: MIME type when using image_base64 ("image/jpeg" or "image/png").
        n: Number of output images (1-10, default: 1).
        aspect_ratio: Output aspect ratio.
        resolution: Output resolution (e.g., "2k").
        response_format: "url" (default) or "b64_json".
        output_dir: Directory to save output images.
    """
    # Resolve image input to URL or data URI
    resolved_url = image_url
    if image_local_path and not resolved_url:
        b64, mime = encode_image_base64(image_local_path)
        resolved_url = f"data:{mime};base64,{b64}"
    elif image_base64 and not resolved_url:
        resolved_url = f"data:{image_mime_type};base64,{image_base64}"

    if not resolved_url:
        return json.dumps({
            "provider": "xai",
            "status": "error",
            "error": "No reference image provided. Use image_url, image_local_path, or image_base64.",
        }, ensure_ascii=False, indent=2)

    result = await _get_xai().generate_image(
        prompt=prompt,
        n=n,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        response_format=response_format,
        image_url=resolved_url,
    )

    # Auto-save images
    save_dir = output_dir or _IMAGE_OUTPUT_DIR
    for img in result.images:
        if img.url:
            try:
                img.saved_path = await save_image_from_url(
                    url=img.url, output_dir=save_dir, prefix="xai_edit",
                )
            except Exception as e:
                logger.error("Failed to download edited image: %s", e)
        elif img.b64_json:
            try:
                img.saved_path = save_image_from_base64(
                    b64_data=img.b64_json, output_dir=save_dir, prefix="xai_edit",
                )
            except Exception as e:
                logger.error("Failed to save base64 image: %s", e)

    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def xai_list_images(
    output_dir: Optional[str] = None,
    limit: int = 20,
) -> str:
    """List recently generated/downloaded images.

    Returns files sorted by newest first with metadata (name, path, size, modified time).

    Args:
        output_dir: Directory to list. Default: ~/xai_output/images.
        limit: Maximum number of files to return (default: 20).
    """
    target_dir = Path(output_dir or _IMAGE_OUTPUT_DIR)
    if not target_dir.exists():
        return json.dumps({
            "output_dir": str(target_dir),
            "count": 0,
            "files": [],
            "note": "Output directory does not exist yet.",
        }, ensure_ascii=False, indent=2)

    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    files = [
        f for f in target_dir.iterdir()
        if f.is_file() and f.suffix.lower() in image_exts
    ]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    files = files[:limit]

    file_list = []
    for f in files:
        stat = f.stat()
        file_list.append({
            "name": f.name,
            "path": str(f),
            "size_kb": round(stat.st_size / 1024, 1),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return json.dumps({
        "output_dir": str(target_dir),
        "count": len(file_list),
        "files": file_list,
    }, ensure_ascii=False, indent=2)


# ===================================================================
# VIDEO GENERATION TOOLS
# ===================================================================


@mcp.tool()
async def xai_generate_video(
    prompt: str,
    model: str = "grok-imagine-video",
    duration: Optional[int] = None,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    image_url: Optional[str] = None,
    image_local_path: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_mime_type: str = "image/jpeg",
) -> str:
    """Generate a video using xAI Grok Imagine (text-to-video or image-to-video).

    Audio (dialogue, SFX, ambient, music) is generated automatically.
    Include spoken dialogue in quotes within the prompt for lip-synced speech.

    Image input supports three methods:
    - Public URL: image_url="https://example.com/photo.jpg"
    - Local file: image_local_path="/path/to/photo.jpg" (auto-encodes)
    - Raw base64: image_base64="..." + image_mime_type="image/jpeg"

    Example prompt: 'A woman in a cafe looks up and says, "I was wondering when
    you would show up." Background jazz music playing softly.'

    Args:
        prompt: Text description of the desired video.
        model: Model identifier (default: "grok-imagine-video").
        duration: Video duration in seconds (1-15).
        aspect_ratio: Aspect ratio ("16:9", "9:16", "1:1"). Default: "16:9".
        resolution: Output resolution (e.g., "720p").
        image_url: Public URL or data URI of a source image.
        image_local_path: Local file path to source image (auto-encodes).
        image_base64: Raw base64-encoded image data.
        image_mime_type: MIME type when using image_base64.
    """
    # Auto-encode local image
    if image_local_path and not image_base64 and not image_url:
        image_base64, image_mime_type = encode_image_base64(image_local_path)

    result = await _get_xai().generate_video(
        prompt=prompt,
        model=model,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        image_url=image_url,
        image_base64=image_base64,
        image_mime_type=image_mime_type,
    )
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def xai_edit_video(
    prompt: str,
    video_url: str,
    model: str = "grok-imagine-video",
) -> str:
    """Edit an existing video using xAI Grok Imagine.

    Supports restyling scenes, adding/removing objects, swapping elements,
    and animating characters. Output keeps the source video's duration,
    aspect ratio, and resolution (max 720p).

    Input constraints: MP4 (H.265/H.264/AV1), max 8.7 seconds.

    Args:
        prompt: Editing instructions describing the desired changes.
        video_url: Public URL of the source video (direct .mp4 link).
        model: Model identifier (default: "grok-imagine-video").
    """
    result = await _get_xai().edit_video(
        prompt=prompt,
        video_url=video_url,
        model=model,
    )
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def xai_check_video_status(request_id: str) -> str:
    """Check the status of an xAI video generation/edit request.

    Video generation is asynchronous (~17 seconds typical).
    Use the request_id from the generation response to check progress.
    Completed requests include temporary download URLs.

    Args:
        request_id: The request ID from the generation/edit response.
    """
    result = await _get_xai().check_video_status(request_id)
    if result.video_urls and result.status != "completed":
        result.status = "completed"
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def xai_wait_for_video(
    request_id: str,
    poll_interval: float = 10.0,
    max_wait: float = 600.0,
) -> str:
    """Wait for an xAI video generation to complete.

    Polls at regular intervals until completion, error, or timeout.
    Completed results include temporary video URLs (download promptly).

    Args:
        request_id: The request ID from the generation response.
        poll_interval: Seconds between checks (default: 10).
        max_wait: Maximum wait time in seconds (default: 600).
    """
    result = await _get_xai().wait_for_video(
        request_id=request_id,
        poll_interval=poll_interval,
        max_wait=max_wait,
    )
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


# ===================================================================
# UTILITY TOOLS
# ===================================================================


@mcp.tool()
async def xai_download_media(
    url: str,
    output_path: Optional[str] = None,
    media_type: str = "image",
) -> str:
    """Download a generated image or video from a temporary URL to local storage.

    xAI returns temporary URLs that expire. Use this to save media locally.

    Args:
        url: The media download URL (from generation result).
        output_path: Local file path to save. If omitted, auto-generates a path
            in the default output directory.
        media_type: "image" or "video" (determines default output directory).
    """
    if not output_path:
        if media_type == "video":
            base_dir = _VIDEO_OUTPUT_DIR
            ext = ".mp4"
            prefix = "xai_vid"
        else:
            base_dir = _IMAGE_OUTPUT_DIR
            ext = ".jpg"
            prefix = "xai_dl"
        from utils.file_utils import _generate_filename
        filename = _generate_filename(prefix, ext)
        output_path = str(Path(base_dir) / filename)

    saved_path = await download_media(url=url, output_path=output_path)
    return json.dumps({
        "status": "downloaded",
        "path": saved_path,
        "media_type": media_type,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def xai_server_info() -> str:
    """Show server environment info for debugging cross-platform issues.

    Reports the current OS, Python version, output directories, and
    whether the xAI API key is configured. Useful for verifying the
    MCP server is running correctly on Windows, Mac Mini, or MacBook.
    """
    has_key = bool(_get_config("xai", "api_key", "XAI_API_KEY"))
    img_dir = Path(_IMAGE_OUTPUT_DIR)
    vid_dir = Path(_VIDEO_OUTPUT_DIR)

    return json.dumps({
        "platform": platform.system(),
        "platform_detail": platform.platform(),
        "python": sys.version.split()[0],
        "hostname": platform.node(),
        "home": str(Path.home()),
        "server_path": str(Path(__file__).parent),
        "config_yaml": str(_config_path),
        "config_yaml_exists": _config_path.exists(),
        "api_key_configured": has_key,
        "image_output_dir": str(img_dir),
        "image_output_exists": img_dir.exists(),
        "video_output_dir": str(vid_dir),
        "video_output_exists": vid_dir.exists(),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def xai_list_models() -> str:
    """List all available xAI models with capabilities and parameters.

    Returns detailed specs for grok-imagine-image and grok-imagine-video.
    """
    models = {
        "image": {
            "model_id": "grok-imagine-image",
            "name": "Grok Imagine Image",
            "endpoint": "POST /v1/images/generations",
            "type": "synchronous",
            "capabilities": [
                "text-to-image",
                "image-editing",
                "style-transfer",
                "multi-turn-editing",
                "batch-generation",
            ],
            "parameters": {
                "n": "1-10 images per request",
                "aspect_ratio": "1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 2:1, 1:2, auto",
                "resolution": "default or 2k",
                "response_format": "url or b64_json",
                "image_url": "Single reference image for editing (URL or data URI)",
            },
            "pricing": "~$0.07 per image (flat rate)",
            "notes": [
                "NEVER use grok-2-image (banned). Always use grok-imagine-image.",
                "Generated URLs are temporary - download immediately.",
                "API accepts only 1 reference image via image_url.",
                "For multiple characters: create a collage first, then reference positions in prompt.",
            ],
        },
        "video": {
            "model_id": "grok-imagine-video",
            "name": "Grok Imagine Video",
            "endpoints": {
                "generate": "POST /v1/videos/generations",
                "edit": "POST /v1/videos/edits",
                "status": "GET /v1/videos/{request_id}",
            },
            "type": "asynchronous (~17 seconds typical)",
            "capabilities": [
                "text-to-video",
                "image-to-video",
                "video-editing",
                "native-audio",
                "lip-sync-dialogue",
                "singing",
            ],
            "parameters": {
                "duration": "1-15 seconds",
                "aspect_ratio": "16:9, 9:16, 1:1",
                "resolution": "720p (max)",
                "image": "Source image URL or data URI for image-to-video",
            },
            "editing_constraints": "MP4 (H.265/H.264/AV1), max 8.7 seconds",
            "notes": [
                "Audio is always generated automatically.",
                "Include dialogue in quotes for lip-synced speech.",
                "Video URLs are temporary - download promptly.",
            ],
        },
    }
    return json.dumps(models, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
