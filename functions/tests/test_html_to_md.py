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


LAYOUT_NEWSLETTER = """
<html><body>
<table width="600"><tr><td>
  <div style="display:none;max-height:0">hidden preheader</div>
  <span>Preheader text&nbsp;&#8204;&nbsp;&#8204;&nbsp;&#8204;&shy;&#8288;&#65279;</span>
  <table><tr>
    <td><a href="https://t.example.com/signup">Sign Up</a></td>
    <td><a href="https://t.example.com/web">View Online</a></td>
  </tr></table>
  <table><tr><td><h2>Headlines</h2></td></tr>
    <tr><td><a href="https://t.example.com/a"><b>Story A (3 minute read)</b></a><br>
      Blurb of story A.</td></tr>
    <tr><td><a href="https://t.example.com/b"><b>Story B (4 minute read)</b></a><br>
      Blurb of story B.</td></tr>
  </table>
  <table>
    <tr><th>Model</th><th>Price</th></tr>
    <tr><td>X</td><td>10</td></tr>
  </table>
  <table><tr><td>
    <a href="https://t.example.com/prefs">Manage your subscriptions</a> to our other newsletters,
    or if this isn't for you, please <a href="https://t.example.com/unsub">unsubscribe</a>.
  </td></tr></table>
  <table><tr><td>Thanks for reading, the team</td></tr></table>
</td></tr></table>
</body></html>
"""


def test_layout_tables_become_readable_paragraphs() -> None:
    md = html_to_markdown(LAYOUT_NEWSLETTER)
    assert md.count("| --- |") == 1  # only the real data table (with <th>) keeps its separator row
    assert "|  |" not in md
    lines = [line for line in md.split("\n") if line.strip()]
    assert len(lines) >= 8  # one block per line, not one giant line
    assert max(len(line) for line in lines) < 200
    assert "\n\n\n" not in md
    assert all(not line.endswith(" ") for line in md.split("\n"))


def test_each_story_is_on_its_own_block_with_its_link() -> None:
    md = html_to_markdown(LAYOUT_NEWSLETTER)
    assert "[**Story A (3 minute read)**](https://t.example.com/a)" in md
    assert "Blurb of story A." in md
    assert md.index("Story A") < md.index("Blurb of story A.") < md.index("Story B")
    assert "[View Online](https://t.example.com/web)" in md
    assert "## Headlines" in md


def test_tables_with_th_cells_are_kept() -> None:
    md = html_to_markdown(LAYOUT_NEWSLETTER)
    assert "| Model | Price |" in md
    assert "| X | 10 |" in md


def test_invisible_characters_and_hidden_blocks_are_removed() -> None:
    md = html_to_markdown(LAYOUT_NEWSLETTER)
    for char in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x00A0):
        assert chr(char) not in md
    assert "hidden preheader" not in md
    assert "Preheader text" in md


def test_orphan_sentence_left_by_unsubscribe_links_is_dropped() -> None:
    md = html_to_markdown(LAYOUT_NEWSLETTER)
    assert "to our other newsletters" not in md
    assert "isn't for you" not in md
    assert "Thanks for reading, the team" in md


def test_tracking_urls_are_left_untouched() -> None:
    url = "https://tracking.example.com/CL0/https:%2F%2Fexample.com%2Fa/1/abc-def/XyZ=452"
    md = html_to_markdown(f'<p><a href="{url}">Story</a></p>')
    assert f"[Story]({url})" in md


def test_non_orphan_text_next_to_a_link_is_kept() -> None:
    html = '<p>Read the full story at <a href="https://x.co/a">our site</a> and enjoy.</p>'
    assert "Read the full story at" in html_to_markdown(html)


def test_code_blocks_keep_their_spacing() -> None:
    md = html_to_markdown("<pre><code>a    b\n  c</code></pre>")
    assert "a    b" in md
