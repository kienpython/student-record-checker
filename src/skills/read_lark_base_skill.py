"""Skill for reading unchecked records from Lark Base."""

import logging
from typing import Any

import requests

from ..lark_auth import LarkAuth


STATUS_FIELD = "Trạng thái"
CHECKED_STATUS = "Đã kiểm tra"


class ReadLarkBaseSkill:
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

    def fetch_records(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return at most ``limit`` records whose status is not checked."""
        if limit < 1:
            return []

        url = (
            f"{self.config.LARK_API_BASE}/bitable/v1"
            f"/apps/{self.config.LARK_APP_TOKEN}"
            f"/tables/{self.config.LARK_TABLE_ID}/records/search"
        )
        payload: dict[str, Any] = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": STATUS_FIELD,
                        "operator": "isNot",
                        "value": [CHECKED_STATUS],
                    }
                ],
            }
        }
        if self.config.LARK_VIEW_ID:
            payload["view_id"] = self.config.LARK_VIEW_ID

        records: list[dict[str, Any]] = []
        page_token: str | None = None

        while len(records) < limit:
            params: dict[str, Any] = {"page_size": min(limit - len(records), 100)}
            if page_token:
                params["page_token"] = page_token

            response = self.session.post(
                url,
                params=params,
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
                    f"Lark search HTTP {response.status_code}: {error_detail}"
                )

            if body.get("code") != 0:
                raise RuntimeError(
                    f"Lark search failed: code={body.get('code')}, "
                    f"msg={body.get('msg', 'Unknown error')}"
                )

            data = body.get("data") or {}
            records.extend(data.get("items") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break

        result = records[:limit]
        self.logger.info("Đã đọc %d record chưa kiểm tra từ Lark Base.", len(result))
        return result

    @staticmethod
    def extract_text(field_value: Any) -> str:
        """Normalize common Lark text/select/number field response shapes."""
        if field_value is None:
            return ""
        if isinstance(field_value, str):
            return field_value.strip()
        if isinstance(field_value, (int, float, bool)):
            return str(field_value)
        if isinstance(field_value, list):
            parts = []
            for item in field_value:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("name") or ""))
                else:
                    parts.append(str(item))
            return "".join(parts).strip()
        if isinstance(field_value, dict):
            return str(
                field_value.get("text")
                or field_value.get("name")
                or field_value.get("value")
                or ""
            ).strip()
        return str(field_value).strip()

    @staticmethod
    def extract_attachments(field_value: Any) -> list[dict[str, Any]]:
        if not isinstance(field_value, list):
            return []
        return [
            item
            for item in field_value
            if isinstance(item, dict)
            and (item.get("file_token") or item.get("attachment_token"))
        ]
