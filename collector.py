import io
import json
import os
import requests
import boto3
from datetime import datetime, timezone

# --- Configuration & Credentials ---
B2_ENDPOINT = os.environ.get('B2_ENDPOINT_URL')
B2_KEY_ID = os.environ.get('B2_ACCESS_KEY_ID')
B2_SECRET_KEY = os.environ.get('B2_SECRET_ACCESS_KEY')
BUCKET_NAME = os.environ.get('B2_BUCKET_NAME', 'kat-gtfs-archive-data')

# Load agency-specific configuration
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

FEEDS = CONFIG.get("feeds", {})


def fetch_and_upload_raw_pb(s3_client, feed_type: str, url: str, now_dt: datetime):
    """Fetches raw Protobuf bytes from a feed URL and uploads directly to B2."""
    print(f"Fetching raw GTFS-RT feed for '{feed_type}'...")
    try:
        response = requests.get(url, timeout=12)
        if response.status_code != 200:
            print(f"[Error] Failed to fetch {feed_type}: HTTP {response.status_code}")
            return
        
        raw_pb_bytes = response.content
        if not raw_pb_bytes:
            print(f"[Warning] Received empty response for {feed_type}")
            return

    except Exception as e:
        print(f"[Error] Failed to connect to {feed_type}: {e}")
        return

    # Create folder partition path:
    # Example: vehicle_positions/2026-09-05/vehicle_positions_20260905_153000.pb
    date_str = now_dt.strftime("%Y-%m-%d")
    ts_str = now_dt.strftime("%Y%m%d_%H%M%S")
    file_key = f"{feed_type}/{date_str}/{feed_type}_{ts_str}.pb"

    # Upload raw binary directly from memory
    print(f"Uploading {file_key} ({len(raw_pb_bytes)} bytes) to Backblaze B2...")
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=file_key,
            Body=raw_pb_bytes,
            ContentType="application/x-protobuf"
        )
        print(f"[Success] Uploaded {file_key}")
    except Exception as e:
        print(f"[Error] Failed to upload {file_key}: {e}")


if __name__ == "__main__":
    now_dt = datetime.now(timezone.utc)
    agency = CONFIG.get("agency_name", "Transit Agency")
    print(f"Scraping {agency} raw feeds at {now_dt.isoformat()}...")

    # Initialize Boto3 S3 Client for Backblaze B2
    s3 = boto3.client(
        service_name="s3",
        endpoint_url=B2_ENDPOINT,
        aws_access_key_id=B2_KEY_ID,
        aws_secret_access_key=B2_SECRET_KEY,
    )

    # Loop over all configured feeds (vehicle_positions, trip_updates, alerts, etc.)
    for feed_type, url in FEEDS.items():
        if url:
            fetch_and_upload_raw_pb(s3, feed_type, url, now_dt)
