import runpod
from runpod.serverless.utils import rp_upload
import os
import re
import shutil
import websocket
import base64
import json
import uuid
import logging
import tempfile
import urllib.request
import urllib.parse
import binascii # Base64 에러 처리를 위해 import
import subprocess
import time
import boto3
from botocore.exceptions import NoCredentialsError
# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hugging Face LoRA cache: repo_id -> (local_path, lora_name for ComfyUI)
_lora_hf_cache = {}
LORA_HF_CACHE_DIR = os.getenv("LORA_HF_CACHE_DIR", "/runpod-volume/loras")


def _sanitize_lora_filename(repo_id):
    """Sanitize HF repo_id to a safe filename (no path, no invalid chars)."""
    name = re.sub(r"[^\w\-.]", "_", repo_id.strip().strip("/"))
    return name if name.lower().endswith(".safetensors") else f"{name}.safetensors"


def get_lora_path_from_hf(repo_id, revision=None, token=None):
    """
    Resolve Hugging Face LoRA repo to a local path under LORA_HF_CACHE_DIR.
    Uses in-memory + on-disk cache: same repo_id returns existing path without re-download.
    Returns (absolute_path, lora_name) where lora_name is the filename for ComfyUI.
    """
    global _lora_hf_cache
    revision = revision or "main"
    cache_key = (repo_id, revision)
    lora_name = _sanitize_lora_filename(repo_id)
    dest_path = os.path.join(LORA_HF_CACHE_DIR, lora_name)

    if cache_key in _lora_hf_cache and os.path.isfile(_lora_hf_cache[cache_key][0]):
        logger.info(f"LoRA cache hit (memory): {repo_id}")
        return _lora_hf_cache[cache_key]

    if os.path.isfile(dest_path):
        _lora_hf_cache[cache_key] = (dest_path, lora_name)
        logger.info(f"LoRA cache hit (disk): {repo_id} -> {lora_name}")
        return (dest_path, lora_name)

    try:
        from huggingface_hub import list_repo_files, hf_hub_download
    except ImportError:
        raise Exception(
            "LoRA from Hugging Face requires 'huggingface_hub'. "
            "Install with: pip install huggingface_hub"
        )

    logger.info(f"Downloading LoRA from Hugging Face: {repo_id} (revision={revision})")
    os.makedirs(LORA_HF_CACHE_DIR, exist_ok=True)
    files = list_repo_files(repo_id, revision=revision, token=token)
    lora_files = [f for f in files if f.lower().endswith(".safetensors")]
    if not lora_files:
        raise Exception(f"No .safetensors file found in repo: {repo_id}")
    first_lora = lora_files[0]
    with tempfile.TemporaryDirectory(prefix="lora_hf_") as tmp:
        src = hf_hub_download(
            repo_id,
            filename=first_lora,
            revision=revision,
            token=token,
            local_dir=tmp,
            local_dir_use_symlinks=False,
        )
        if not os.path.isfile(src):
            src = os.path.join(tmp, first_lora)
        shutil.copy2(src, dest_path)
    _lora_hf_cache[cache_key] = (dest_path, lora_name)
    logger.info(f"LoRA cached: {repo_id} -> {dest_path}")
    return (dest_path, lora_name)


server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())

def to_nearest_multiple_of_16(value):
    """Correct the given value to the nearest multiple of 16, ensuring a minimum of 16"""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height values are not numbers: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted

def process_input(input_data, temp_dir, output_filename, input_type):
    """Function to process input data and return the file path"""
    if input_type == "path":
        # Return path directly
        logger.info(f"📁 Processing path input: {input_data}")
        return input_data
    elif input_type == "url":
        # Download from URL
        logger.info(f"🌐 Processing URL input: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        # Decode Base64 and save
        logger.info(f"🔢 Processing Base64 input")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"Unsupported input type: {input_type}")

        
def download_file_from_url(url, output_path):
    """Function to download a file from a URL"""
    try:
        # Download file using wget
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ Successfully downloaded file from URL: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget download failed: {result.stderr}")
            raise Exception(f"URL download failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ Download timeout")
        raise Exception("Download timeout")
    except Exception as e:
        logger.error(f"❌ Error occurred during download: {e}")
        raise Exception(f"Error occurred during download: {e}")


def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Function to save Base64 data to a file"""
    try:
        # Decode Base64 string
        decoded_data = base64.b64decode(base64_data)
        
        # Create directory if it doesn't exist
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save to file
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"✅ Saved Base64 input to file '{file_path}'.")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 decoding failed: {e}")
        raise Exception(f"Base64 decoding failed: {e}")
    
R2_KEY_PREFIX = "temporary"


def upload_to_r2(image_data, file_name):
    """
    Upload image data to Cloudflare R2 and return the URL.
    Objects are stored under key prefix: temporary/zimage/
    Requires environment variables R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME.
    """
    try:
        account_id = os.environ.get('R2_ACCOUNT_ID')
        access_key = os.environ.get('R2_ACCESS_KEY_ID')
        secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
        bucket_name = os.environ.get('R2_BUCKET_NAME')
        custom_domain = os.environ.get('R2_CUSTOM_DOMAIN') or os.environ.get('R2_PUBLIC_URL')

        if not all([account_id, access_key, secret_key, bucket_name]):
            logger.error("Environment variables for R2 upload are not set.")
            return None

        key = f"{R2_KEY_PREFIX}/zimage/{file_name}"

        s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        # Base64 디코딩
        if isinstance(image_data, str):
            try:
                image_bytes = base64.b64decode(image_data)
            except binascii.Error:
                image_bytes = image_data.encode('utf-8')
        else:
            image_bytes = image_data

        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=image_bytes,
            ContentType='image/png'
        )
        
        if custom_domain:
            url = f"{custom_domain.rstrip('/')}/{key}"
            if not url.startswith("http"):
                 url = f"https://{url}"
            logger.info(f"✅ R2 upload successful (Public URL): {url}")
            return url
        else:
            # Generate Presigned URL if no Custom Domain (valid for 1 hour)
            try:
                url = s3_client.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={'Bucket': bucket_name, 'Key': key},
                    ExpiresIn=3600
                )
                logger.info(f"✅ R2 upload successful (Presigned URL): {url}")
                return url
            except Exception as e:
                logger.error(f"❌ Failed to generate Presigned URL: {e}")
                return None

    except Exception as e:
        logger.error(f"❌ Error occurred during R2 upload: {e}")
        return None

def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    logger.info(f"Getting image from: {url}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                # bytes 객체를 base64로 인코딩하여 JSON 직렬화 가능하게 변환
                if isinstance(image_data, bytes):
                    import base64
                    image_data = base64.b64encode(image_data).decode('utf-8')
                images_output.append(image_data)
        output_images[node_id] = images_output

    return output_images

def load_workflow(workflow_path):
    """워크플로우 파일을 로드하는 함수"""
    # 상대 경로인 경우 현재 파일 기준으로 절대 경로 변환
    if not os.path.isabs(workflow_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        workflow_path = os.path.join(current_dir, workflow_path)
    with open(workflow_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def handler(job):
    job_input = job.get("input", {})

    logger.info(f"Received job input: {job_input}")
    task_id = f"task_{uuid.uuid4()}"

    # Process condition image input (use one of condition_image, condition_image_path, condition_image_url, condition_image_base64)
    condition_image_path = None
    if "condition_image" in job_input:
        # Automatically detect type if condition_image parameter is provided
        condition_image_data = job_input["condition_image"]
        if isinstance(condition_image_data, str):
            if condition_image_data.startswith("http://") or condition_image_data.startswith("https://"):
                condition_image_path = process_input(condition_image_data, task_id, "condition_image.jpg", "url")
            elif os.path.exists(condition_image_data) or condition_image_data.startswith("/"):
                condition_image_path = process_input(condition_image_data, task_id, "condition_image.jpg", "path")
            else:
                # Treated as Base64
                condition_image_path = process_input(condition_image_data, task_id, "condition_image.jpg", "base64")
        else:
            raise Exception("condition_image parameter must be a string.")
    elif "condition_image_path" in job_input:
        condition_image_path = process_input(job_input["condition_image_path"], task_id, "condition_image.jpg", "path")
    elif "condition_image_url" in job_input:
        condition_image_path = process_input(job_input["condition_image_url"], task_id, "condition_image.jpg", "url")
    elif "condition_image_base64" in job_input:
        condition_image_path = process_input(job_input["condition_image_base64"], task_id, "condition_image.jpg", "base64")

    # Check LoRA: support Hugging Face repo (with cache) or local lora list
    lora_list = job_input.get("lora", [])
    lora_repo = job_input.get("lora_repo")
    lora_scale = float(job_input.get("lora_scale", 1.0))
    if lora_repo:
        try:
            _, lora_name = get_lora_path_from_hf(
                lora_repo,
                revision=job_input.get("lora_revision"),
                token=os.environ.get("HF_TOKEN"),
            )
            lora_list = [[lora_name, lora_scale]]
        except Exception as e:
            logger.error(f"Failed to resolve LoRA from HF: {lora_repo}: {e}")
            raise
    has_lora = lora_list and len(lora_list) > 0
    
    # Select workflow file (Priority: condition_image > lora > default)
    if condition_image_path:
        workflow_file = "workflow/z_image_control.json"
        logger.info(f"Using control workflow: {workflow_file}")
    elif has_lora:
        workflow_file = "workflow/z_image_lora.json"
        logger.info(f"Using LoRA workflow: {workflow_file}")
    else:
        workflow_file = "workflow/z_image.json"
        logger.info(f"Using text-only workflow: {workflow_file}")

    prompt = load_workflow(workflow_file)

    # Common settings
    prompt_text = job_input.get("prompt", "")
    seed = job_input.get("seed", 533303727624653)
    steps = job_input.get("steps", 9)
    cfg = job_input.get("cfg", 1.0)
    width = job_input.get("width", 1024)
    height = job_input.get("height", 1024)
    negative_prompt = job_input.get("negative_prompt", "")
    
    # Correct resolution (width/height) to multiples of 16
    adjusted_width = to_nearest_multiple_of_16(width)
    adjusted_height = to_nearest_multiple_of_16(height)
    if adjusted_width != width:
        logger.info(f"Width adjusted to nearest multiple of 16: {width} -> {adjusted_width}")
    if adjusted_height != height:
        logger.info(f"Height adjusted to nearest multiple of 16: {height} -> {adjusted_height}")

    if condition_image_path:
        # z_image_control.json workflow configuration
        # Node 58: LoadImage (condition image)
        prompt["58"]["inputs"]["image"] = condition_image_path
        
        # Node 70:45: CLIPTextEncode (prompt)
        prompt["70:45"]["inputs"]["text"] = prompt_text
        
        # Node 70:44: KSampler (seed, steps, cfg)
        prompt["70:44"]["inputs"]["seed"] = seed
        prompt["70:44"]["inputs"]["steps"] = steps
        prompt["70:44"]["inputs"]["cfg"] = cfg
        
        # Node 57: Canny (low_threshold, high_threshold) - optional
        if "canny_low_threshold" in job_input:
            prompt["57"]["inputs"]["low_threshold"] = job_input["canny_low_threshold"]
        if "canny_high_threshold" in job_input:
            prompt["57"]["inputs"]["high_threshold"] = job_input["canny_high_threshold"]
        
        # Node 70:60: QwenImageDiffsynthControlnet (strength) - optional
        if "controlnet_strength" in job_input:
            prompt["70:60"]["inputs"]["strength"] = job_input["controlnet_strength"]
        
        # Node 70:41: EmptySD3LatentImage takes size automatically from 70:69, so no setting required
        
        logger.info(f"Control workflow configuration complete: condition_image={condition_image_path}, prompt={prompt_text[:50]}...")
    elif has_lora:
        # z_image_lora.json workflow configuration
        # Node 58: PrimitiveStringMultiline (prompt)
        prompt["58"]["inputs"]["value"] = prompt_text
        
        # Node 59:13: EmptySD3LatentImage (width, height)
        prompt["59:13"]["inputs"]["width"] = adjusted_width
        prompt["59:13"]["inputs"]["height"] = adjusted_height
        
        # Node 59:3: KSampler (seed, steps, cfg)
        prompt["59:3"]["inputs"]["seed"] = seed
        prompt["59:3"]["inputs"]["steps"] = steps
        prompt["59:3"]["inputs"]["cfg"] = cfg
        
        # Node 59:35: LoraLoaderModelOnly (lora_name, strength_model)
        # Use only the first LoRA (multiple support possible later)
        first_lora = lora_list[0]
        if isinstance(first_lora, list) and len(first_lora) >= 2:
            lora_path = first_lora[0]
            lora_strength = first_lora[1]
        else:
            raise Exception("Invalid LoRA format. Should be [file_path, strength].")
        
        prompt["59:35"]["inputs"]["lora_name"] = lora_path
        prompt["59:35"]["inputs"]["strength_model"] = lora_strength
        
        logger.info(f"LoRA workflow configuration complete: lora={lora_path}, strength={lora_strength}, prompt={prompt_text[:50]}...")
    else:
        # z_image.json workflow configuration
        # Node 45: CLIPTextEncode (prompt)
        prompt["45"]["inputs"]["text"] = prompt_text
        
        # Node 44: KSampler (seed, steps, cfg)
        prompt["44"]["inputs"]["seed"] = seed
        prompt["44"]["inputs"]["steps"] = steps
        prompt["44"]["inputs"]["cfg"] = cfg
        
        # Node 41: EmptySD3LatentImage (width, height)
        prompt["41"]["inputs"]["width"] = adjusted_width
        prompt["41"]["inputs"]["height"] = adjusted_height
        
        logger.info(f"Text-only workflow configuration complete: prompt={prompt_text[:50]}...")

    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")
    
    # 먼저 HTTP 연결이 가능한지 확인
    http_url = f"http://{server_address}:8188/"
    logger.info(f"Checking HTTP connection to: {http_url}")
    
    # HTTP 연결 확인 (최대 1분)
    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            import urllib.request
            response = urllib.request.urlopen(http_url, timeout=5)
            logger.info(f"HTTP 연결 성공 (시도 {http_attempt+1})")
            break
        except Exception as e:
            logger.warning(f"HTTP 연결 실패 (시도 {http_attempt+1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("ComfyUI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            time.sleep(1)
    
    ws = websocket.WebSocket()
    # 웹소켓 연결 시도 (최대 3분)
    max_attempts = int(180/5)  # 3분 (5초에 한 번씩 시도)
    for attempt in range(max_attempts):
        try:
            ws.connect(ws_url)
            logger.info(f"웹소켓 연결 성공 (시도 {attempt+1})")
            break
        except Exception as e:
            logger.warning(f"웹소켓 연결 실패 (시도 {attempt+1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("웹소켓 연결 시간 초과 (3분)")
            time.sleep(5)
    images = get_images(ws, prompt)
    ws.close()

    # Handle case where no images are generated
    if not images:
        return {"error": "Cannot generate image."}
    
    # Return the first image
    for node_id in images:
        if images[node_id]:
            image_data = images[node_id][0]
            
            if job_input.get("return_url", False):
                # R2 upload
                file_name = f"{task_id}.png"
                image_url = upload_to_r2(image_data, file_name)
                if image_url:
                    return {"image_url": image_url}
                else:
                     logger.warning("R2 upload failed, returning Base64 image.")

            return {"image": image_data}
    
    return {"error": "Image not found."}

runpod.serverless.start({"handler": handler})