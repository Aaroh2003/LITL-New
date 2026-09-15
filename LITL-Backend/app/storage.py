import re
from urllib.parse import parse_qs, quote, urlparse

from .config import MAX_FILE_BYTES
from .network import RemoteError, bounded_request, request_json


class SupabaseStorage:
    def __init__(self, settings, client):
        self.base = settings.supabase_url + "/storage/v1"
        self.bucket = settings.storage_bucket
        self.client = client
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": "Bearer " + settings.supabase_service_role_key,
        }

    def path(self, key):
        if not re.fullmatch(r"[a-f0-9-]{36}/[a-f0-9-]{36}\.(?:pdf|docx|txt)", key):
            raise RemoteError("Invalid internal storage key")
        return quote(self.bucket, safe="") + "/" + key

    def validate_bucket(self):
        data = request_json(self.client, "GET", self.base + "/bucket/" + quote(self.bucket, safe=""),
                            headers=self.headers, limit=65536)
        limit = data.get("file_size_limit")
        if data.get("public") is not False or not isinstance(limit, int) or not 0 < limit <= MAX_FILE_BYTES:
            raise RemoteError("Storage bucket must be private with a file-size limit of at most 10 MiB")

    def sign_upload(self, key):
        expected_path = "/object/upload/sign/" + self.path(key)
        data = request_json(self.client, "POST", self.base + expected_path, headers=self.headers, json={})
        signed = data.get("url", "")
        parsed = urlparse(signed)
        token = parse_qs(parsed.query).get("token", [])
        if (parsed.scheme or parsed.netloc or parsed.path != expected_path or
                not token or len(token[0]) > 4096):
            raise RemoteError("Storage returned an unexpected signed upload URL")
        return {
            "upload_url": self.base + signed,
            "upload_headers": {"Content-Type": "application/octet-stream", "x-upsert": "false"},
        }

    def download(self, key):
        return bounded_request(
            self.client, "GET", self.base + "/object/authenticated/" + self.path(key),
            headers=self.headers, limit=MAX_FILE_BYTES,
        )

    def delete(self, key):
        bounded_request(self.client, "DELETE", self.base + "/object/" + quote(self.bucket, safe=""),
                        headers=self.headers, json={"prefixes": [key]}, limit=65536)
