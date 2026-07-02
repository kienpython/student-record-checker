"""Skill to download Lark attachment files.

Uses the Download Media endpoint:
  GET /open-apis/drive/v1/medias/{file_token}/download

Saves files to cache/files/{record_id}/.
"""

import logging
from pathlib import Path
from typing import Optional

import requests

from ..lark_auth import LarkAuth


class LarkFileHandlerSkill:
    """Downloads Lark Bitable attachments using file tokens."""

    def __init__(self, *, config, auth: LarkAuth, logger: Optional[logging.Logger] = None):
        self.config = config
        self.auth = auth
        self.logger = logger or logging.getLogger(__name__)
        self.cache_dir: Path = Path(self.config.CACHE_FILES)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_by_token(
        self,
        file_token: str,
        filename: str,
        record_id: str,
    ) -> Optional[Path]:
        """Download a Lark attachment and save to cache.

        Args:
            file_token: The Lark file_token from the attachment object.
            filename: Original filename (for extension detection).
            record_id: Used to organize cache directory.

        Returns:
            Path to the downloaded file, or None on failure.
        """
        # Check cache first
        record_dir = self.cache_dir / record_id
        record_dir.mkdir(parents=True, exist_ok=True)
        dest = record_dir / filename

        if dest.exists() and dest.stat().st_size > 0:
            self.logger.info(f"Cache hit: {dest}")
            return dest

        url = (
            f"{self.config.LARK_API_BASE}/drive/v1"
            f"/medias/{file_token}/download"
        )

        # Include extra param for advanced permissions
        params = {
            "extra": f'{{"bitablePerm":{{"tableId":"{self.config.LARK_TABLE_ID}"}}}}'
        }

        try:
            headers = self.auth.get_headers()
            # Remove Content-Type for file download
            headers.pop("Content-Type", None)

            resp = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=120,
                stream=True,
            )
            resp.raise_for_status()

            # Check if response is JSON error instead of file content
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                body = resp.json()
                self.logger.error(
                    f"Lark download error for {file_token}: "
                    f"code={body.get('code')}, msg={body.get('msg')}"
                )
                return None

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.logger.info(f"Downloaded {filename} ({dest.stat().st_size} bytes) → {dest}")
            return dest

        except requests.RequestException as e:
            self.logger.error(f"Failed to download {file_token}: {e}")
            return None
