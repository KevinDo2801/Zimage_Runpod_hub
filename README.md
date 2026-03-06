# Z-Image Turbo for RunPod Serverless

Template to run **Z-Image Turbo** on RunPod Serverless. Z-Image Turbo is a fast, high-quality image generation model based on the Z-Image architecture.

[![Runpod](https://api.runpod.io/badge/wlsdml1114/Flux-krea_Runpod_hub)](https://console.runpod.io/hub/wlsdml1114/Flux-krea_Runpod_hub)

---

## Engui Studio

[![EnguiStudio](https://raw.githubusercontent.com/wlsdml1114/Engui_Studio/main/assets/banner.png)](https://github.com/wlsdml1114/Engui_Studio)

Designed to work with **Engui Studio** (AI model management). Usable via API; Engui Studio adds a UI and broader model support.

---

## Features

- **Text-to-image** – prompt-only generation
- **LoRA** – local files or Hugging Face repos (with disk cache)
- **ControlNet (Canny)** – structure/edge conditioning
- **ComfyUI** – workflow-based; workflows in `workflow/`
- **R2** – optional upload to Cloudflare R2 and return URL

---

## Deployment

1. Create a Serverless Endpoint on RunPod from this repo/image.
2. Send jobs via HTTP POST to the endpoint with JSON `input` as below.

---

## Input Parameters

All parameters live under the request `input` object.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | string | Yes | `""` | Text prompt for the image. |
| `seed` | integer | No | `533303727624653` | Random seed. |
| `steps` | integer | No | `9` | Sampling steps. |
| `cfg` | float | No | `1.0` | Classifier-free guidance scale. |
| `width` | integer | No | `1024` | Output width (adjusted to multiple of 16). |
| `height` | integer | No | `1024` | Output height (adjusted to multiple of 16). |
| `negative_prompt` | string | No | `""` | Negative prompt (workflow-dependent). |
| `lora` | array | No | `[]` | Local LoRAs: `[[ "path_or_filename", strength ], ...]`. Only first entry used. |
| `lora_repo` | string | No | - | Hugging Face LoRA repo ID (e.g. `user/repo`). Downloaded and cached under `LORA_HF_CACHE_DIR`. |
| `lora_scale` | float | No | `1.0` | LoRA strength when using `lora_repo`. |
| `lora_revision` | string | No | `main` | Git revision for `lora_repo`. |
| `condition_image` | string | No | - | ControlNet image: URL, file path, or base64. Type auto-detected. |
| `condition_image_path` | string | No | - | ControlNet image as file path. |
| `condition_image_url` | string | No | - | ControlNet image as URL. |
| `condition_image_base64` | string | No | - | ControlNet image as base64. |
| `controlnet_strength` | float | No | - | ControlNet strength (when using condition image). |
| `canny_low_threshold` | number | No | - | Canny edge low threshold. |
| `canny_high_threshold` | number | No | - | Canny edge high threshold. |
| `return_url` | boolean | No | `false` | If `true`, upload output to R2 and return `image_url` (requires R2 env). |

**Workflow choice:** `condition_image` (or path/url/base64) → ControlNet; else `lora` or `lora_repo` → LoRA; else text-only.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SERVER_ADDRESS` | No | ComfyUI server host (default `127.0.0.1`). |
| `LORA_HF_CACHE_DIR` | No | Directory for cached HF LoRA files (default `/runpod-volume/loras`). |
| `HF_TOKEN` | No | Hugging Face token for private/gated LoRA repos. |
| `R2_ACCOUNT_ID` | For R2 | Cloudflare R2 account ID. |
| `R2_ACCESS_KEY_ID` | For R2 | R2 access key. |
| `R2_SECRET_ACCESS_KEY` | For R2 | R2 secret key. |
| `R2_BUCKET_NAME` | For R2 | R2 bucket name. |
| `R2_CUSTOM_DOMAIN` | No | Custom domain for public URLs (optional). |

---

## Output

- **Success (base64):** `{ "image": "<base64 string>" }`
- **Success (R2):** `{ "image_url": "https://..." }` when `return_url` is true and R2 is configured.
- **Error:** `{ "error": "<message>" }`

---

## Example Requests

**Text-to-image**
```json
{
  "input": {
    "prompt": "A futuristic city in the style of cyberpunk",
    "width": 1024,
    "height": 1024,
    "steps": 10
  }
}
```

**LoRA from Hugging Face (cached)**
```json
{
  "input": {
    "prompt": "a portrait in custom style",
    "lora_repo": "username/lora-model-name",
    "lora_scale": 0.9
  }
}
```

**LoRA from local path** (file under ComfyUI loras paths, e.g. `models/loras/` or `/runpod-volume/loras/`)
```json
{
  "input": {
    "prompt": "a cat in anime style",
    "lora": [["my_style.safetensors", 0.8]]
  }
}
```

**ControlNet (condition image as URL)**
```json
{
  "input": {
    "prompt": "a beautiful landscape",
    "condition_image": "https://example.com/edge_map.jpg",
    "controlnet_strength": 0.8
  }
}
```

**ControlNet (condition image as base64)**
```json
{
  "input": {
    "prompt": "same structure, different scene",
    "condition_image_base64": "<base64 string>",
    "controlnet_strength": 0.7,
    "canny_low_threshold": 0.1,
    "canny_high_threshold": 0.2
  }
}
```

**Return URL via R2**
```json
{
  "input": {
    "prompt": "a sunset over mountains",
    "return_url": true
  }
}
```

---

## License

This project follows the licenses of Z-Image Turbo and ComfyUI.
