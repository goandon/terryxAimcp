# Terry xAI MCP Server

Unified MCP server for xAI image and video generation.

- **Image**: `grok-imagine-image` — text-to-image, image editing, style transfer
- **Video**: `grok-imagine-video` — text-to-video, image-to-video, video editing

Cross-platform: Windows, macOS, Linux.

## Setup

### Prerequisites

- Python 3.10+
- xAI API key ([platform.x.ai](https://platform.x.ai))

### Install

```bash
git clone https://github.com/goandon/terryxAimcp.git
cd terryxAimcp
pip install -r requirements.txt
```

### Configuration

Set your API key via environment variable (recommended) or `config.yaml`:

```bash
# Linux / macOS
export XAI_API_KEY="xai-your-key-here"

# Windows (PowerShell)
$env:XAI_API_KEY = "xai-your-key-here"
```

Optional output directories (default: `~/xai_output/images` and `~/xai_output/videos`):

```bash
export XAI_IMAGE_OUTPUT_DIR="/path/to/images"
export XAI_VIDEO_OUTPUT_DIR="/path/to/videos"
```

Alternatively, edit `config.yaml` directly:

```yaml
xai:
  api_key: "xai-your-key-here"

output:
  image_dir: "/path/to/images"
  video_dir: "/path/to/videos"
```

Environment variables always take precedence over `config.yaml`.

## MCP Client Registration

### Claude Desktop

Add to your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "terry-xai": {
      "command": "python3",
      "args": ["/absolute/path/to/terryxAimcp/server.py"],
      "env": {
        "XAI_API_KEY": "xai-your-key-here"
      }
    }
  }
}
```

> **Windows note**: Use the full Python path if `python3` is not in PATH:
> `"command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python3xx\\python.exe"`

### Claude Code

Add to project `.mcp.json` or `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "terry-xai": {
      "command": "python3",
      "args": ["/absolute/path/to/terryxAimcp/server.py"],
      "env": {
        "PYTHONDONTWRITEBYTECODE": "1",
        "XAI_API_KEY": "xai-your-key-here"
      }
    }
  }
}
```

### OpenClaw / Other MCP Clients

Any MCP client that supports stdio transport can use this server.
Point it to `server.py` with the environment variables above.

## Tools Reference (10 tools)

### Image Tools

| Tool | Description |
|------|-------------|
| `xai_generate_image` | Text-to-image generation (1-10 images, various aspect ratios) |
| `xai_edit_image` | Image editing with reference image (URL, local path, or base64) |
| `xai_list_images` | List recently generated images with metadata |

### Video Tools

| Tool | Description |
|------|-------------|
| `xai_generate_video` | Text/image-to-video with auto audio generation |
| `xai_edit_video` | Edit existing video (restyle, add/remove objects) |
| `xai_check_video_status` | Check async video generation status |
| `xai_wait_for_video` | Poll until video generation completes |

### Utility Tools

| Tool | Description |
|------|-------------|
| `xai_download_media` | Download from temporary URL to local storage |
| `xai_list_models` | List available xAI models with capabilities |
| `xai_server_info` | Show server platform, paths, and config status |

## Usage Examples

### Generate an image

```
prompt: "A serene mountain landscape at sunset with warm amber tones"
aspect_ratio: "16:9"
```

### Edit an image with reference

```
prompt: "Transform to watercolor painting style"
image_local_path: "/path/to/photo.jpg"
```

### Generate a video with dialogue

```
prompt: 'A woman in a cafe looks up and says, "I was wondering when you would show up." Background jazz music playing softly.'
duration: 8
aspect_ratio: "16:9"
```

### Image-to-video

```
prompt: "Camera slowly zooms in as wind blows through her hair"
image_local_path: "/path/to/character.jpg"
duration: 10
```

## Cross-Platform Notes

| Topic | Detail |
|-------|--------|
| **File paths** | All code uses `pathlib.Path` — OS path separators handled automatically |
| **Output dirs** | Default `~/xai_output/` resolves via `Path.home()` on all platforms |
| **HTTP client** | Uses `httpx` (async). Works on Windows, macOS, and Linux |
| **WSL** | xAI image API may return Cloudflare 1010 errors from WSL. Use native Windows Python instead |
| **Verify setup** | Call `xai_server_info` tool to check platform, paths, and API key status |

## API Reference

### Image API (`grok-imagine-image`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | **Required.** Text description or editing instruction |
| `n` | int | Number of images (1-10, default: 1) |
| `aspect_ratio` | string | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `2:1`, `1:2`, `auto` |
| `resolution` | string | `"2k"` or omit for default |
| `image_url` | string | Reference image for editing (1 image only, URL or data URI) |

- Synchronous API — results returned immediately
- Cost: ~$0.07 per image (flat rate)
- **Important**: Always use `grok-imagine-image`. Do NOT use `grok-2-image`.

### Video API (`grok-imagine-video`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | **Required.** Include dialogue in quotes for lip-sync |
| `duration` | int | 1-15 seconds |
| `aspect_ratio` | string | `16:9`, `9:16`, `1:1` |
| `resolution` | string | `720p` (max) |
| `image` | object | Source image for image-to-video (URL or data URI) |

- Asynchronous API — returns `request_id`, poll with `xai_check_video_status` or `xai_wait_for_video`
- Audio always generated automatically (dialogue, SFX, ambient)
- Typical generation time: ~17 seconds
- Video editing input: MP4 (H.265/H.264/AV1), max 8.7 seconds

## Important Notes

- Generated image/video URLs are **temporary** — they are auto-saved locally by default.
- Image API accepts only 1 reference image. For multiple characters, create a collage first.
- Video URLs should be downloaded promptly before they expire.

## License

MIT

## Author

Terry kim <goandonh@gmail.com>
Co-Author: Claudie
