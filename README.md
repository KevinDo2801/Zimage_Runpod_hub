# Z-Image Turbo for RunPod Serverless

This project is a template designed to easily deploy and use **Z-Image Turbo** in the RunPod Serverless environment.

[![Runpod](https://api.runpod.io/badge/wlsdml1114/Flux-krea_Runpod_hub)](https://console.runpod.io/hub/wlsdml1114/Flux-krea_Runpod_hub)

Z-Image Turbo is an advanced AI model designed for ultra-fast, high-quality image generation and editing, based on the Z-Image architecture.

## 🎨 Engui Studio Integration

[![EnguiStudio](https://raw.githubusercontent.com/wlsdml1114/Engui_Studio/main/assets/banner.png)](https://github.com/wlsdml1114/Engui_Studio)

This template is primarily designed for **Engui Studio**, a comprehensive AI model management platform. While it can be used via API, Engui Studio provides enhanced features and broader model support.

## ✨ Key Features

*   **Ultra-Fast Generation**: Optimized for speed with the "Turbo" architecture.
*   **Text-to-Image**: High-quality generation from text prompts.
*   **LoRA Support**: Support for LoRA models to customize styles.
*   **ControlNet (Canny)**: Control image generation using structural input (edges/Canny).
*   **Cloudflare R2 Integration**: Optionally upload results directly to R2.
*   **ComfyUI-Based**: Built on ComfyUI for flexible and powerful workflows.

## 🚀 RunPod Serverless Template

This template includes all components to run Z-Image Turbo as a RunPod Serverless Worker.

### Input Parameters

The `input` object can contain the following fields:

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `prompt` | `string` | **Yes** | `""` | Description of the image to generate. |
| `seed` | `integer` | No | `533303727624653` | Random seed for generation. |
| `steps` | `integer` | No | `9` | Number of sampling steps. |
| `cfg` | `float` | No | `1.0` | Classifier-Free Guidance scale. |
| `width` | `integer` | No | `1024` | Width of the output image. |
| `height` | `integer` | No | `1024` | Height of the output image. |
| `lora` | `array` | No | `[]` | List of LoRAs: `[[path, strength]]`. |
| `condition_image` | `string` | No | `null` | Image for ControlNet (URL, Path, or Base64). |
| `controlnet_strength` | `float` | No | `null` | Strength of the ControlNet effect. |
| `return_url` | `boolean` | No | `false` | If true, uploads to R2 and returns a URL. |

### Output

#### Success (Base64)
```json
{
  "image": "data:image/png;base64,..."
}
```

#### Success (URL - Requires R2 config)
```json
{
  "image_url": "https://..."
}
```

## 🛠️ Usage

1.  Create a Serverless Endpoint on RunPod using this image/repository.
2.  Submit jobs via HTTP POST to the endpoint.

### Example Request (Text-to-Image)
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

### Example Request (ControlNet)
```json
{
  "input": {
    "prompt": "a beautiful landscape",
    "condition_image": "https://example.com/edge_map.jpg",
    "controlnet_strength": 0.8
  }
}
```

## 📄 License

This project follows the licenses of Z-Image Turbo and ComfyUI.
