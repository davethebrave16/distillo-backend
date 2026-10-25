from distillo.ingest.html_to_md import html_to_markdown, plain_text_to_markdown

HTML = """
<html><head><style>p{color:red}</style><title>t</title></head><body>
<a href="https://example.com/web">View in browser</a>
<h2>Big news</h2>
<p><a href="https://example.com/a">Article A</a> is out.</p>
<img src="https://cdn.example.com/p.gif" width="1" height="1">
<img src="https://track.example.com/open.png" alt="x">
<img src="https://cdn.example.com/hero.png" alt="Hero chart">
<img src="https://cdn.example.com/deco.png">
<p>Some more content here.</p>
<p>You are receiving this email because you subscribed.</p>
<p><a href="https://example.com/unsub">Unsubscribe</a> |
<a href="https://x.co/prefs">Manage preferences</a></p>
</body></html>
"""


def test_keeps_content_links_and_view_in_browser() -> None:
    md = html_to_markdown(HTML)
    assert "[View in browser](https://example.com/web)" in md
    assert "## Big news" in md
    assert "[Article A](https://example.com/a)" in md
    assert "![Hero chart]" in md


def test_removes_tracking_images_and_boilerplate() -> None:
    md = html_to_markdown(HTML)
    assert "p.gif" not in md
    assert "track.example.com" not in md
    assert "deco.png" not in md
    assert "color:red" not in md
    assert "unsubscribe" not in md.lower()
    assert "Manage preferences" not in md
    assert "You are receiving" not in md


def test_collapses_blank_lines() -> None:
    assert "\n\n\n" not in html_to_markdown("<p>a</p><br><br><br><p>b</p>")


def test_footer_marker_early_in_document_is_kept() -> None:
    text = "Unsubscribe from nothing: this is the intro.\n" + "line\n" * 20
    assert plain_text_to_markdown(text).startswith("Unsubscribe from nothing")


def test_plain_text_footer_is_cut() -> None:
    text = "Intro\n" + "content line\n" * 20 + "You are receiving this because...\nbye"
    out = plain_text_to_markdown(text)
    assert "You are receiving" not in out
    assert out.startswith("Intro")
