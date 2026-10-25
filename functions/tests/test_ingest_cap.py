from typing import Any

from distillo.ingest.gmail import list_message_ids
from distillo.ingest.service import select_new_ids


def test_existing_ids_do_not_consume_the_cap() -> None:
    ids = [f"m{i}" for i in range(10)]  # newest first
    existing = {"m0", "m1", "m2", "m3", "m4"}
    to_process, deferred = select_new_ids(ids, existing, max_messages=3)
    assert to_process == ["m5", "m6", "m7"]
    assert deferred == 2


def test_repeated_runs_make_progress_through_older_mail() -> None:
    ids = [f"m{i}" for i in range(7)]
    stored: set[str] = set()
    runs = 0
    while True:
        batch, _ = select_new_ids(ids, stored, max_messages=3)
        if not batch:
            break
        stored.update(batch)
        runs += 1
    assert stored == set(ids)
    assert runs == 3


def test_nothing_deferred_when_under_cap() -> None:
    assert select_new_ids(["a", "b"], {"a"}, max_messages=50) == (["b"], 0)


class _FakeMessages:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages
        self.calls: list[dict[str, Any]] = []

    def list(self, **kwargs: Any) -> "_FakeMessages":
        self.calls.append(kwargs)
        self._page = self.pages[len(self.calls) - 1]
        return self

    def execute(self) -> dict[str, Any]:
        return self._page


class _FakeGmail:
    def __init__(self, messages: _FakeMessages) -> None:
        self._messages = messages

    def users(self) -> "_FakeGmail":
        return self

    def messages(self) -> _FakeMessages:
        return self._messages


def test_list_message_ids_follows_pagination_to_the_end() -> None:
    pages = [
        {"messages": [{"id": "a"}, {"id": "b"}], "nextPageToken": "t1"},
        {"messages": [{"id": "c"}]},
    ]
    fake = _FakeMessages(pages)
    assert list_message_ids(_FakeGmail(fake), "label:news") == ["a", "b", "c"]
    assert fake.calls[1]["pageToken"] == "t1"


def test_list_message_ids_stops_at_the_hard_limit() -> None:
    pages = [{"messages": [{"id": f"m{i}"} for i in range(5)], "nextPageToken": "t"}] * 5
    assert len(list_message_ids(_FakeGmail(_FakeMessages(pages)), "q", limit=7)) == 7
