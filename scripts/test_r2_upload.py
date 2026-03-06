"""
One-off script to test R2 upload. Loads .env from project root and uploads a small file to runpod-hub/temporary/zimage/
"""
import os
import sys
import boto3

# Project root = parent of scripts/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

def load_dotenv(path=".env"):
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_dotenv()

account_id = os.environ.get("R2_ACCOUNT_ID")
access_key = os.environ.get("R2_ACCESS_KEY_ID")
secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
bucket_name = os.environ.get("R2_BUCKET_NAME")

if not all([account_id, access_key, secret_key, bucket_name]):
    print("Missing R2_* env vars. Set them in .env or environment.")
    sys.exit(1)

key_prefix = "temporary/zimage"
key = f"{key_prefix}/test-upload.txt"
body = b"R2 upload test from Zimage_Runpod_hub\n"

client = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name="auto",
)

client.put_object(Bucket=bucket_name, Key=key, Body=body, ContentType="text/plain")
print(f"Upload OK: s3://{bucket_name}/{key}")

try:
    url = client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=3600,
    )
    print(f"Presigned URL (1h): {url[:80]}...")
except Exception as e:
    print(f"Presigned URL failed: {e}")
