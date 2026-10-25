import importlib.util
import stat
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gmail_auth.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gmail_auth", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALUES = {"GMAIL_CLIENT_ID": "id", "GMAIL_CLIENT_SECRET": "sec", "GMAIL_REFRESH_TOKEN": "tok"}


def test_creates_missing_file_with_mode_600(tmp_path: Path) -> None:
    path = tmp_path / ".secret.local"
    _load().update_env_file(path, VALUES)
    assert path.read_text().splitlines() == [f"{k}={v}" for k, v in VALUES.items()]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_updates_only_the_three_keys_and_preserves_other_lines(tmp_path: Path) -> None:
    path = tmp_path / ".secret.local"
    path.write_text("# comment\nOTHER=keep\nGMAIL_CLIENT_ID=\nGMAIL_REFRESH_TOKEN=old\n\nTAIL=1\n")
    path.chmod(0o644)

    _load().update_env_file(path, VALUES)

    assert path.read_text().splitlines() == [
        "# comment",
        "OTHER=keep",
        "GMAIL_CLIENT_ID=id",
        "GMAIL_REFRESH_TOKEN=tok",
        "",
        "TAIL=1",
        "GMAIL_CLIENT_SECRET=sec",
    ]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_duplicate_keys_collapse_to_one(tmp_path: Path) -> None:
    path = tmp_path / ".secret.local"
    path.write_text("GMAIL_CLIENT_ID=a\nGMAIL_CLIENT_ID=b\n")
    _load().update_env_file(path, VALUES)
    assert path.read_text().count("GMAIL_CLIENT_ID=") == 1
