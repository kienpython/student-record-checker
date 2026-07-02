"""Skill for updating only comment and status fields in Lark Base."""

import logging
from typing import Any

import requests

from ..lark_auth import LarkAuth


COMMENT_FIELD = "Nhận xét"
STATUS_FIELD = "Trạng thái"


class UpdateLarkBaseSkill:
    def __init__(
        self,
        *,
        config: Any,
        auth: LarkAuth,
        logger: logging.Logger | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.auth = auth
        self.logger = logger or logging.getLogger(__name__)
        self.session = session or requests.Session()

    def update_record(
        self,
        *,
        record_id: str,
        comment: str,
        status: str,
        dry_run: bool = False,
    ) -> bool:
        payload = {
            "fields": {
                COMMENT_FIELD: comment,
                STATUS_FIELD: status,
            }
        }
        if dry_run:
            self.logger.info("[DRY RUN] %s <- %s", record_id, payload["fields"])
            return True

        url = (
            f"{self.config.LARK_API_BASE}/bitable/v1"
            f"/apps/{self.config.LARK_APP_TOKEN}"
            f"/tables/{self.config.LARK_TABLE_ID}/records/{record_id}"
        )
        response = self.session.put(
            url,
            json=payload,
            headers=self.auth.get_headers(),
            timeout=30,
        )
        try:
            body = response.json()
        except ValueError:
            body = {}

        if not response.ok:
            error_detail = (
                f"code={body.get('code')}, msg={body.get('msg')}"
                if body
                else response.text[:500]
            )
            raise RuntimeError(
                f"Lark update HTTP {response.status_code}: {error_detail}"
            )

        if body.get("code") != 0:
            raise RuntimeError(
                f"Lark update failed: code={body.get('code')}, "
                f"msg={body.get('msg', 'Unknown error')}"
            )
        self.logger.info("Đã cập nhật record %s.", record_id)
        return True
