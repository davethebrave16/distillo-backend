"""Pydantic models for Firestore documents (camelCase in Firestore, snake_case in Python)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

EmailStatus = Literal["pending", "extracted", "unmatched", "skipped", "error"]


class FirestoreModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def to_firestore(self) -> dict[str, object]:
        """Dict with camelCase keys, omitting unset optional fields."""
        return self.model_dump(by_alias=True, exclude_none=True)


class SourceSettingsDoc(FirestoreModel):
    """sourceSettings/{sourceId}"""

    enabled: bool
    updated_at: datetime


class EmailDoc(FirestoreModel):
    """emails/{gmailMessageId}"""

    source_id: str | None
    from_address: str = Field(alias="from")  # `from` is a Python keyword
    subject: str
    received_at: datetime
    markdown: str
    status: EmailStatus
    error: str | None = None
    item_ids: list[str] = Field(default_factory=list)
