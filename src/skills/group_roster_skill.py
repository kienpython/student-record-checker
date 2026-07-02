"""Skill for resolving expected group size from class roster text files."""

import logging
from pathlib import Path
import re


GROUP_ID_PATTERN = re.compile(r"^(?P<class_code>.+)-(?P<group>G\d+)$", re.IGNORECASE)
ROSTER_LINE_PATTERN = re.compile(
    r"^\s*(?P<group>G\d+)\s*:\s*(?P<count>\d+)\s*(?:sinh\s*viên)?\s*$",
    re.IGNORECASE,
)


class GroupRosterSkill:
    def __init__(
        self,
        *,
        config,
        logger: logging.Logger | None = None,
    ) -> None:
        self.class_dir = Path(config.CLASS_DIR)
        self.logger = logger or logging.getLogger(__name__)

    def expected_speakers(self, group_id: str) -> int | None:
        """Return roster size for IDs like ``HN-KS25-CNTT4-G3``."""
        match = GROUP_ID_PATTERN.match(group_id.strip())
        if not match:
            self.logger.warning("Group ID không đúng định dạng lớp-Gx: %r", group_id)
            return None

        class_code = match.group("class_code")
        group_code = match.group("group").upper()
        roster_file = self.class_dir / class_code / f"{class_code}.txt"
        if not roster_file.exists():
            self.logger.warning("Không tìm thấy file sĩ số: %s", roster_file)
            return None

        for line in roster_file.read_text(encoding="utf-8-sig").splitlines():
            line_match = ROSTER_LINE_PATTERN.match(line)
            if (
                line_match
                and line_match.group("group").upper() == group_code
            ):
                count = int(line_match.group("count"))
                self.logger.info(
                    "%s có %d sinh viên theo %s.",
                    group_id,
                    count,
                    roster_file.name,
                )
                return count

        self.logger.warning(
            "Không tìm thấy %s trong file %s.",
            group_code,
            roster_file,
        )
        return None
