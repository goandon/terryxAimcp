"""
Unified xAI provider for image and video generation.

Supports:
  - Image generation via grok-imagine-image (synchronous)
  - Video generation via grok-imagine-video (asynchronous with polling)
  - Video editing via grok-imagine-video (asynchronous with polling)

Author: Terry kim <goandonh@gmail.com>
Co-Author: Claudie
"""

import asyncio
import json
import logging
from typing import Optional

import httpx

from models.schemas import (
    ImageGenerationResult,
    ImageResult,
    VideoGenerationResult,
    XaiImageEditRequest,
    XaiImageModel,
    XaiImageRequest,
    XaiVideoEditRequest,
    XaiVideoGenRequest,
    XaiVideoModel,
)

logger = logging.getLogger(__name__)

_XAI_BASE = "https://api.x.ai/v1"


class XaiProvider:
    """Unified client for xAI image and video generation APIs.

    Image generation (grok-imagine-image):
      - Synchronous: returns image URLs or base64 data immediately
      - Supports text-to-image and image editing (with reference image_url)

    Video generation (grok-imagine-video):
      - Asynchronous: returns request_id, poll for completion
      - Supports text-to-video, image-to-video, and video editing
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=120.0)

    def _headers(self) -> dict:
        if not self.api_key:
            raise RuntimeError(
                "xAI API key is not set. "
                "Set XAI_API_KEY environment variable or configure config.yaml."
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ==================================================================
    # IMAGE GENERATION
    # ==================================================================

    async def generate_image(
        self,
        prompt: str,
        n: int = 1,
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None,
        response_format: str = "url",
        image_url: Optional[str] = None,
    ) -> ImageGenerationResult:
        """Generate images or edit an image using grok-imagine-image.

        When image_url is provided, the API performs image editing/style transfer.
        The API accepts only 1 reference image via image_url.

        Args:
            prompt: Text description or editing instruction.
            n: Number of images to generate (1-10).
            aspect_ratio: Image aspect ratio (e.g., "16:9", "1:1").
            resolution: Output resolution (e.g., "2k").
            response_format: "url" for temporary URLs, "b64_json" for base64 data.
            image_url: Reference image URL for editing/style transfer.
                Supports public URL, data URI, or base64 data URI.
        """
        req = XaiImageRequest(
            prompt=prompt,
            model=XaiImageModel.GROK_IMAGINE_IMAGE.value,
            n=n,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            response_format=response_format,
            image_url=image_url,
        )
        body = req.to_api_body()
        url = f"{_XAI_BASE}/images/generations"

        logger.info("xAI generate_image -> n=%d, aspect_ratio=%s", n, aspect_ratio)
        logger.debug("Request body: %s", json.dumps(body, indent=2))

        resp = await self._client.post(url, json=body, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        logger.debug("xAI image response keys: %s", list(data.keys()))

        return self._parse_image_response(data)

    @staticmethod
    def _parse_image_response(data: dict) -> ImageGenerationResult:
        """Parse xAI image generation API response."""
        result = ImageGenerationResult(
            status="completed",
            raw_response=data,
        )

        # Extract revised prompt if present
        if "revised_prompt" in data:
            result.revised_prompt = data["revised_prompt"]

        # Extract image data from response
        items = data.get("data", [])
        if not isinstance(items, list):
            items = [items]

        for item in items:
            if not isinstance(item, dict):
                continue
            img = ImageResult(
                url=item.get("url"),
                b64_json=item.get("b64_json"),
                revised_prompt=item.get("revised_prompt"),
            )
            result.images.append(img)

            # Capture first revised_prompt at result level
            if img.revised_prompt and not result.revised_prompt:
                result.revised_prompt = img.revised_prompt

        if not result.images:
            result.status = "error"
            result.error = "No images returned in response"
            if "error" in data:
                err = data["error"]
                result.error = err.get("message", str(err)) if isinstance(err, dict) else str(err)

        return result

    # ==================================================================
    # IMAGE EDITING (multi-reference)
    # ==================================================================

    async def edit_image(
        self,
        prompt: str,
        image_urls: list[str],
        n: int = 1,
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None,
        response_format: str = "url",
    ) -> ImageGenerationResult:
        """Edit or create images using up to 3 reference images.

        Uses the /v1/images/edits endpoint which supports multiple references.
        Can be used for editing, compositing, and reference-guided generation.

        Args:
            prompt: Editing instruction or generation description.
            image_urls: List of reference image URLs (max 3). Supports
                public URLs and data URIs (base64).
            n: Number of output images (1-10).
            aspect_ratio: Output aspect ratio.
            resolution: Output resolution (e.g., "2k").
            response_format: "url" or "b64_json".
        """
        if len(image_urls) > 3:
            raise ValueError("xAI /v1/images/edits supports at most 3 reference images")

        req = XaiImageEditRequest(
            prompt=prompt,
            n=n,
            image_urls=image_urls,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            response_format=response_format,
        )
        body = req.to_api_body()
        url = f"{_XAI_BASE}/images/edits"

        logger.info(
            "xAI edit_image -> n=%d, refs=%d, aspect_ratio=%s",
            n, len(image_urls), aspect_ratio,
        )
        logger.debug("Request body keys: %s", list(body.keys()))

        resp = await self._client.post(url, json=body, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        logger.debug("xAI edit response keys: %s", list(data.keys()))

        return self._parse_image_response(data)

    # ==================================================================
    # VIDEO GENERATION
    # ==================================================================

    async def generate_video(
        self,
        prompt: str,
        model: str = XaiVideoModel.GROK_IMAGINE_VIDEO.value,
        duration: Optional[int] = None,
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mime_type: str = "image/jpeg",
    ) -> VideoGenerationResult:
        """Generate a video from text prompt, optionally with a source image.

        Audio (dialogue, SFX, ambient) is always generated automatically.
        Include dialogue in quotes within the prompt for lip-synced speech.

        Args:
            prompt: Text description of the desired video.
            model: Model identifier (default: grok-imagine-video).
            duration: Video duration in seconds (1-15).
            aspect_ratio: Aspect ratio ("16:9", "9:16", "1:1").
            resolution: Output resolution (e.g., "720p").
            image_url: Public URL or data URI of source image.
            image_base64: Raw base64-encoded image data.
            image_mime_type: MIME type when using image_base64.
        """
        req = XaiVideoGenRequest(
            model=model,
            prompt=prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            image_url=image_url,
            image_base64=image_base64,
            image_mime_type=image_mime_type,
        )
        body = req.to_api_body()
        url = f"{_XAI_BASE}/videos/generations"

        logger.info("xAI generate_video -> model=%s, duration=%s", model, duration)
        logger.debug("Request body: %s", json.dumps(body, indent=2))

        resp = await self._client.post(url, json=body, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        logger.debug("xAI video response: %s", json.dumps(data, indent=2, ensure_ascii=False))

        return self._parse_video_response(data)

    async def edit_video(
        self,
        prompt: str,
        video_url: str,
        model: str = XaiVideoModel.GROK_IMAGINE_VIDEO.value,
    ) -> VideoGenerationResult:
        """Edit an existing video based on prompt instructions.

        Input constraints: MP4 (H.265/H.264/AV1), max 8.7 seconds.
        Output retains source duration, aspect ratio, resolution (max 720p).

        Args:
            prompt: Editing instructions (restyle, add/remove objects, etc.)
            video_url: Public URL of the source video.
            model: Model identifier.
        """
        req = XaiVideoEditRequest(
            model=model,
            prompt=prompt,
            video_url=video_url,
        )
        body = req.to_api_body()
        url = f"{_XAI_BASE}/videos/edits"

        logger.info("xAI edit_video -> model=%s", model)
        logger.debug("Request body: %s", json.dumps(body, indent=2))

        resp = await self._client.post(url, json=body, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        logger.debug("xAI edit response: %s", json.dumps(data, indent=2, ensure_ascii=False))

        return self._parse_video_response(data)

    # ==================================================================
    # VIDEO STATUS POLLING
    # ==================================================================

    async def check_video_status(self, request_id: str) -> VideoGenerationResult:
        """Check the status of an async video generation/edit request."""
        url = f"{_XAI_BASE}/videos/{request_id}"

        resp = await self._client.get(url, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        return self._parse_video_response(data)

    async def wait_for_video(
        self,
        request_id: str,
        poll_interval: float = 10.0,
        max_wait: float = 600.0,
    ) -> VideoGenerationResult:
        """Poll until video generation completes or timeout.

        Args:
            request_id: The request ID from generation response.
            poll_interval: Seconds between status checks.
            max_wait: Maximum wait time in seconds.
        """
        elapsed = 0.0
        while elapsed < max_wait:
            result = await self.check_video_status(request_id)
            if result.video_urls:
                result.status = "completed"
                return result
            if result.status in ("completed", "error"):
                return result
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return VideoGenerationResult(
            status="timeout",
            request_id=request_id,
            error=f"Request did not complete within {max_wait}s",
        )

    # ==================================================================
    # VIDEO RESPONSE PARSING
    # ==================================================================

    @staticmethod
    def _parse_video_response(data: dict) -> VideoGenerationResult:
        """Parse xAI video API response into unified result."""
        status_raw = data.get("status", "unknown")

        status_map = {
            "InProgress": "pending",
            "pending": "pending",
            "done": "completed",
            "Completed": "completed",
            "completed": "completed",
            "expired": "error",
            "Failed": "error",
            "failed": "error",
        }
        if status_raw == "unknown" and "request_id" in data:
            status = "pending"
        else:
            status = status_map.get(status_raw, status_raw)

        result = VideoGenerationResult(
            status=status,
            request_id=data.get("request_id") or data.get("id"),
            raw_response=data,
        )

        # Extract video URLs from various response formats
        video_data = data.get("data", data.get("video", data.get("output")))
        if isinstance(video_data, list):
            for item in video_data:
                if isinstance(item, dict) and "url" in item:
                    result.video_urls.append(item["url"])
        elif isinstance(video_data, dict) and "url" in video_data:
            result.video_urls.append(video_data["url"])

        if "url" in data and data["url"]:
            result.video_urls.append(data["url"])

        # Upgrade status if video URLs found
        if result.video_urls and result.status not in ("completed", "error"):
            result.status = "completed"

        # Handle error responses
        if "error" in data:
            result.status = "error"
            err = data["error"]
            result.error = err.get("message", str(err)) if isinstance(err, dict) else str(err)

        return result

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
