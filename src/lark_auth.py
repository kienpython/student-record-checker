"""Lark tenant_access_token manager.

Obtains and caches a tenant_access_token using LARK_APP_ID + LARK_APP_SECRET.
The token is valid for 2 hours; we refresh when it has < 5 minutes left.
"""

import logging
import time
from typing import Optional

import requests


class LarkAuth:
    """Manages Lark tenant_access_token lifecycle."""

    TOKEN_URL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    # Refresh the token when it has less than this many seconds left
    REFRESH_MARGIN_SECONDS = 300  # 5 minutes

    def __init__(self, app_id: str, app_secret: str, logger: Optional[logging.Logger] = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.logger = logger or logging.getLogger(__name__)
        self._token: Optional[str] = None
        self._expires_at: float = 0.0  # epoch timestamp

    def get_token(self) -> str:
        """Return a valid tenant_access_token, refreshing if necessary."""
        if self._token and time.time() < (self._expires_at - self.REFRESH_MARGIN_SECONDS):
            return self._token
        self._refresh()
        return self._token

    def _refresh(self) -> None:
        """Request a new tenant_access_token from Lark."""
        self.logger.debug("Requesting new tenant_access_token...")
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        try:
            resp = requests.post(
                self.TOKEN_URL,
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                msg = f"Lark auth error: code={data.get('code')}, msg={data.get('msg')}"
                self.logger.error(msg)
                raise RuntimeError(msg)

            self._token = data["tenant_access_token"]
            expire_secs = data.get("expire", 7200)
            self._expires_at = time.time() + expire_secs
            self.logger.info(
                f"Obtained tenant_access_token (expires in {expire_secs}s)"
            )
        except requests.RequestException as e:
            self.logger.error(f"Failed to obtain tenant_access_token: {e}")
            raise

    def get_headers(self) -> dict:
        """Return standard headers with a valid Bearer token."""
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }
