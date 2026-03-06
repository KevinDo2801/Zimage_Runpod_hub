# Zimage for RunPod Serverless

RunPod Serverless worker for **Zimage** (ComfyUI-based image generation) with text-to-image, LoRA (including Hugging Face), and control-image (Canny + ControlNet) workflows.

## Key Features

* **Text-to-image**: Prompt-only generation via `workflow/z_image.json`.
* **LoRA**: Single LoRA via `workflow/z_image_lora.json` — local path or **Hugging Face** repo (cached under `LORA_HF_CACHE_DIR`).
* **Control image**: Condition image (path / URL / base64) with Canny + ControlNet via `workflow/z_image_control.json`.
* **Workflow selection**: Automatic by input: condition image → control workflow; LoRA only → LoRA workflow; else text-only.
* **Output**: Base64 `image` in response, or **Cloudflare R2** upload with `image_url` when `return_url: true` and R2 env configured.
* **Resolution**: `width` / `height` are normalized to the nearest multiple of 16 (min 16).

## Input

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `prompt` | `string` | Yes | `""` | Text prompt for image generation. |
| `seed` | `integer` | No | `533303727624653` | Random seed. |
| `steps` | `integer` | No | `9` | Sampling steps. |
| `cfg` | `float` | No | `1.0` | CFG scale. |
| `width` | `integer` | No | `1024` | Image width (adjusted to multiple of 16). |
| `height` | `integer` | No | `1024` | Image height (adjusted to multiple of 16). |
| `negative_prompt` | `string` | No | `""` | Negative prompt. |
| `condition_image` | `string` | No | — | Condition image: URL, path, or base64 (auto-detected). |
| `condition_image_path` | `string` | No | — | Condition image as file path. |
| `condition_image_url` | `string` | No | — | Condition image as URL. |
| `condition_image_base64` | `string` | No | — | Condition image as base64. |
| `canny_low_threshold` | `number` | No | — | Canny edge low threshold (control workflow). |
| `canny_high_threshold` | `number` | No | — | Canny edge high threshold (control workflow). |
| `controlnet_strength` | `number` | No | — | ControlNet strength (control workflow). |
| `lora` | `array` | No | `[]` | LoRA list: `[[path_or_name, strength], ...]` (one used in current workflow). |
| `lora_repo` | `string` | No | — | Hugging Face LoRA repo ID (e.g. `user/repo`). Uses first `.safetensors` in repo. |
| `lora_revision` | `string` | No | `main` | Hugging Face repo revision. |
| `lora_scale` | `float` | No | `1.0` | LoRA strength when using `lora_repo`. |
| `return_url` | `boolean` | No | `false` | If `true` and R2 configured, return `image_url` instead of base64 `image`. |

**LoRA**

* Local/volume: `lora` = `[["/path/to/lora.safetensors", 0.8]]`.
* Hugging Face: set `lora_repo` (and optionally `lora_revision`, `lora_scale`). Requires `huggingface_hub`. Optional `HF_TOKEN` for private repos. Cache directory: `LORA_HF_CACHE_DIR` (default `/runpod-volume/loras`).

**Request examples**

Text-only:

```json
{
  "input": {
    "prompt": "a beautiful landscape with mountains and a lake",
    "seed": 12345,
    "width": 1024,
    "height": 1024
  }
}
```

With Hugging Face LoRA:

```json
{
  "input": {
    "prompt": "a beautiful landscape",
    "lora_repo": "username/lora-repo-name",
    "lora_scale": 0.8
  }
}
```

With condition image (URL):

```json
{
  "input": {
    "prompt": "same style, different scene",
    "condition_image_url": "https://example.com/reference.jpg",
    "controlnet_strength": 0.9
  }
}
```

Return image URL via R2:

```json
{
  "input": {
    "prompt": "a cat",
    "return_url": true
  }
}
```

## Output

**Success**

| Field | Type | Description |
| --- | --- | --- |
| `image` | `string` | Base64-encoded image (default). |
| `image_url` | `string` | Present when `return_url: true` and R2 upload succeeds; public or presigned URL. |

**Error**

| Field | Type | Description |
| --- | --- | --- |
| `error` | `string` | Error message. |

Example success (base64):

```json
{
  "image": "data:image/png;base64,iVBORw0KGgo..."
}
```

Example success (R2 URL):

```json
{
  "image_url": "https://your-r2-domain.com/temporary/task_xxx.png"
}
```

## Cloudflare R2 (optional)

When `return_url: true`, the handler uploads the image to R2 and returns `image_url`. If upload fails, it falls back to base64 `image`.

**Environment variables**

| Variable | Required | Description |
| --- | --- | --- |
| `R2_ACCOUNT_ID` | Yes | R2 account ID. |
| `R2_ACCESS_KEY_ID` | Yes | R2 access key. |
| `R2_SECRET_ACCESS_KEY` | Yes | R2 secret key. |
| `R2_BUCKET_NAME` | Yes | Bucket name. |
| `R2_CUSTOM_DOMAIN` hoặc `R2_PUBLIC_URL` | No | Custom domain / public URL cho ảnh (vd. `https://pub-xxx.r2.dev`). Không set thì trả presigned URL (1h). |

Objects are stored under the `temporary/` prefix.

**Test script**

```bash
python scripts/test_r2_upload.py
```

Uses `.env` in project root for R2 credentials.

## Workflow files

| File | Use case |
| --- | --- |
| `workflow/z_image.json` | Text-only. |
| `workflow/z_image_lora.json` | Single LoRA (local path or HF cache name). |
| `workflow/z_image_control.json` | Condition image + Canny + QwenImageDiffsynthControlnet. |

ComfyUI is expected at `SERVER_ADDRESS:8188` (default `127.0.0.1:8188`).

## RunPod setup

1. Create a Serverless Endpoint from this repo.
2. Set env vars as needed: R2 (if using `return_url`), `HF_TOKEN` (private HF LoRA), `LORA_HF_CACHE_DIR`.
3. Send HTTP POST requests to the endpoint with `input` as above.

## License

See repository and upstream ComfyUI / model licenses.
