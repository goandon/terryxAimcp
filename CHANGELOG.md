# Changelog

## v0.2.0 (2026-03-05)

### Added
- **Multi-reference image editing**: `xai_edit_image` now uses `/v1/images/edits` endpoint supporting up to 3 reference images
- **Reference-guided generation**: Use character sheets as references to generate new images with consistent character identity
- **`XaiImageEditRequest` schema**: New dataclass for `/v1/images/edits` with `images` array support
- **`edit_image()` provider method**: New method in `XaiProvider` for multi-reference editing
- **`image_local_paths` parameter**: Pass multiple local file paths to `xai_edit_image` (auto-encoded to data URIs)
- **`image_urls` parameter**: Pass multiple image URLs to `xai_edit_image`
- **`image_url` / `image_local_path` on `xai_generate_image`**: Optional single reference image for guided generation via `/v1/images/generations`

### Changed
- `xai_edit_image` endpoint changed from `/v1/images/generations` to `/v1/images/edits`
- `xai_edit_image` now merges single-image and multi-image params (max 3 total)
- `xai_list_models` updated to reflect dual-endpoint architecture and new capabilities
- README updated with multi-reference examples and dual API documentation

## v0.1.0 (2026-03-02)

### Added
- Initial release
- Image generation via `grok-imagine-image` (text-to-image, single-image editing)
- Video generation via `grok-imagine-video` (text-to-video, image-to-video)
- Video editing (restyle, add/remove objects)
- Cross-platform support (Windows, macOS, Linux)
- Auto-download of generated media to local storage
- 10 MCP tools: generate, edit, list, download, status, wait, server info, list models
