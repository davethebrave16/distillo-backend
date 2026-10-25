from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from distillo.ingest.mime import decode_gmail_raw

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TOKEN_URI = "https://oauth2.googleapis.com/token"
_PAGE_SIZE = 100
LIST_HARD_LIMIT = 2000  # safety bound on listed IDs; the per-run processing cap is separate


def build_gmail_service(client_id: str, client_secret: str, refresh_token: str) -> Any:
    credentials = Credentials(  # type: ignore[no-untyped-call]
        token=None,  # fetched through the refresh token on first call
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[GMAIL_SCOPE],
    )
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def list_message_ids(service: Any, query: str, limit: int = LIST_HARD_LIMIT) -> list[str]:
    """Message IDs matching `query` (newest first), following pagination up to `limit`."""
    ids: list[str] = []
    page_token: str | None = None
    while len(ids) < limit:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(_PAGE_SIZE, limit - len(ids)),
                pageToken=page_token,
            )
            .execute()
        )
        ids.extend(m["id"] for m in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return ids[:limit]


def get_raw_message(service: Any, message_id: str) -> bytes:
    response = service.users().messages().get(userId="me", id=message_id, format="raw").execute()
    return decode_gmail_raw(response["raw"])
