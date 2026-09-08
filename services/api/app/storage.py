"""Private Supabase Storage adapter."""

from urllib.parse import quote

import httpx


class StorageError(RuntimeError):
    """Raised when Supabase Storage rejects an operation."""


class SupabaseStorage:
    def __init__(self, supabase_url: str, secret_key: str, bucket: str, *, http_client=None):
        self.base_url = supabase_url.rstrip("/")
        self.secret_key = secret_key
        self.bucket = bucket
        self.http_client = http_client or httpx.Client(timeout=60.0)

    def upload(self, object_path: str, content: bytes, content_type: str) -> None:
        encoded_path = quote(object_path, safe="/")
        response = self.http_client.post(
            f"{self.base_url}/storage/v1/object/{quote(self.bucket)}/{encoded_path}",
            headers={
                "apikey": self.secret_key,
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": content_type,
                "x-upsert": "false",
            },
            content=content,
        )
        if response.status_code not in (200, 201):
            raise StorageError(f"Supabase Storage upload failed ({response.status_code})")

    def remove(self, object_paths: list[str]) -> None:
        response = self.http_client.request(
            "DELETE",
            f"{self.base_url}/storage/v1/object/{quote(self.bucket)}",
            headers={
                "apikey": self.secret_key,
                "Authorization": f"Bearer {self.secret_key}",
            },
            json={"prefixes": object_paths},
        )
        if response.status_code not in (200, 204):
            raise StorageError(f"Supabase Storage cleanup failed ({response.status_code})")

    def download(self, object_path: str) -> bytes:
        encoded_path = quote(object_path, safe="/")
        response = self.http_client.get(
            f"{self.base_url}/storage/v1/object/authenticated/{quote(self.bucket)}/{encoded_path}",
            headers={
                "apikey": self.secret_key,
                "Authorization": f"Bearer {self.secret_key}",
            },
        )
        if response.status_code != 200:
            raise StorageError(f"Supabase Storage download failed ({response.status_code})")
        return response.content
