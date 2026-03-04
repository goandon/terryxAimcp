"""
Data models for xAI image and video generation APIs.

Covers grok-imagine-image (synchronous image generation) and
grok-imagine-video (asynchronous video generation/editing).

Author: Terry kim <goandonh@gmail.com>
Co-Author: Claudie
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class XaiImageModel(str, Enum):
    GROK_IMAGINE_IMAGE = "grok-imagine-image"


class XaiVideoModel(str, Enum):
    GROK_IMAGINE_VIDEO = "grok-imagine-video"


class ImageAspectRatio(str, Enum):
    """Supported aspect ratios for grok-imagine-image."""
    SQUARE = "1:1"
    LANDSCAPE_16_9 = "16:9"
    PORTRAIT_9_16 = "9:16"
    LANDSCAPE_4_3 = "4:3"
    PORTRAIT_3_4 = "3:4"
    LANDSCAPE_3_2 = "3:2"
    PORTRAIT_2_3 = "2:3"
    LANDSCAPE_2_1 = "2:1"
    PORTRAIT_1_2 = "1:2"
    AUTO = "auto"


class VideoAspectRatio(str, Enum):
    """Supported aspect ratios for grok-imagine-video."""
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"
    SQUARE = "1:1"


# ---------------------------------------------------------------------------
# Image generation dataclasses
# ---------------------------------------------------------------------------

@dataclass
class XaiImageRequest:
    """xAI image generation request (text-to-image or single-image editing).

    API endpoint: POST https://api.x.ai/v1/images/generations
    Model: grok-imagine-image (NEVER use grok-2-image)

    When image_url is provided, the API performs image editing/style transfer.
    The API accepts only 1 reference image via image_url.
    """
    prompt: str = ""
    model: str = XaiImageModel.GROK_IMAGINE_IMAGE.value
    n: int = 1
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    response_format: str = "url"
    image_url: Optional[str] = None

    def to_api_body(self) -> dict:
        d: dict = {
            "model": self.model,
            "prompt": self.prompt,
            "n": self.n,
            "response_format": self.response_format,
        }
        if self.aspect_ratio:
            d["aspect_ratio"] = self.aspect_ratio
        if self.resolution:
            d["resolution"] = self.resolution
        if self.image_url:
            d["image_url"] = self.image_url
        return d


@dataclass
class XaiImageEditRequest:
    """xAI image editing request with multiple reference images.

    API endpoint: POST https://api.x.ai/v1/images/edits
    Model: grok-imagine-image

    Supports up to 3 reference images via image_urls.
    Can be used for editing, style transfer, compositing, and
    reference-guided generation (creating new images using references as guide).
    """
    prompt: str = ""
    model: str = XaiImageModel.GROK_IMAGINE_IMAGE.value
    n: int = 1
    image_urls: list[str] = field(default_factory=list)
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    response_format: str = "url"

    def to_api_body(self) -> dict:
        d: dict = {
            "model": self.model,
            "prompt": self.prompt,
            "n": self.n,
            "response_format": self.response_format,
        }
        if self.aspect_ratio:
            d["aspect_ratio"] = self.aspect_ratio
        if self.resolution:
            d["resolution"] = self.resolution
        if self.image_urls:
            d["images"] = [
                {"url": url, "type": "image_url"} for url in self.image_urls
            ]
        return d


@dataclass
class ImageResult:
    """Single generated image result."""
    url: Optional[str] = None
    b64_json: Optional[str] = None
    saved_path: Optional[str] = None
    revised_prompt: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {}
        if self.url:
            d["url"] = self.url
        if self.b64_json:
            d["b64_json_length"] = len(self.b64_json)
        if self.saved_path:
            d["saved_path"] = self.saved_path
        if self.revised_prompt:
            d["revised_prompt"] = self.revised_prompt
        return d


@dataclass
class ImageGenerationResult:
    """Result from xAI image generation."""
    status: str = ""
    images: list[ImageResult] = field(default_factory=list)
    revised_prompt: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[dict] = None

    def to_dict(self) -> dict:
        d: dict = {"provider": "xai", "status": self.status}
        if self.images:
            d["images"] = [img.to_dict() for img in self.images]
            d["count"] = len(self.images)
        if self.revised_prompt:
            d["revised_prompt"] = self.revised_prompt
        if self.error:
            d["error"] = self.error
        if self.raw_response:
            # Exclude large base64 data from raw response
            filtered = {k: v for k, v in self.raw_response.items() if k != "data"}
            if filtered:
                d["raw_response"] = filtered
        return d


# ---------------------------------------------------------------------------
# Video generation dataclasses
# ---------------------------------------------------------------------------

@dataclass
class XaiVideoGenRequest:
    """xAI video generation request (text-to-video or image-to-video).

    API endpoint: POST https://api.x.ai/v1/videos/generations
    Model: grok-imagine-video

    Audio (dialogue, SFX, ambient, music) is always generated.
    Include dialogue in quotes within the prompt for lip-synced speech.
    """
    model: str = XaiVideoModel.GROK_IMAGINE_VIDEO.value
    prompt: str = ""
    duration: Optional[int] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    image_mime_type: str = "image/jpeg"

    def _resolve_image_url(self) -> Optional[str]:
        if self.image_url:
            return self.image_url
        if self.image_base64:
            return f"data:{self.image_mime_type};base64,{self.image_base64}"
        return None

    def to_api_body(self) -> dict:
        d: dict = {"model": self.model, "prompt": self.prompt}
        if self.duration is not None:
            d["duration"] = self.duration
        if self.aspect_ratio:
            d["aspect_ratio"] = self.aspect_ratio
        if self.resolution:
            d["resolution"] = self.resolution
        resolved_url = self._resolve_image_url()
        if resolved_url:
            d["image"] = {"url": resolved_url}
        return d


@dataclass
class XaiVideoEditRequest:
    """xAI video editing request (video-to-video).

    API endpoint: POST https://api.x.ai/v1/videos/edits
    Input constraints: MP4 (H.265/H.264/AV1), max 8.7 seconds.
    """
    model: str = XaiVideoModel.GROK_IMAGINE_VIDEO.value
    prompt: str = ""
    video_url: str = ""

    def to_api_body(self) -> dict:
        return {
            "model": self.model,
            "prompt": self.prompt,
            "video": {"url": self.video_url},
        }


@dataclass
class VideoGenerationResult:
    """Result from xAI video generation/editing."""
    status: str = ""
    request_id: Optional[str] = None
    video_urls: list[str] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[dict] = None

    def to_dict(self) -> dict:
        d: dict = {"provider": "xai", "status": self.status}
        if self.request_id:
            d["request_id"] = self.request_id
        if self.video_urls:
            d["video_urls"] = self.video_urls
        if self.error:
            d["error"] = self.error
        if self.raw_response:
            d["raw_response"] = self.raw_response
        return d
