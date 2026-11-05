"""Model text shown on a page as written."""

import re

import pytest

from hindcast.escape import code, plain


def test_plain_escapes_a_link_and_an_image():
    from hindcast.escape import WORD_JOINER

    shown = r"\!\[x\]\(https" + WORD_JOINER + r"://e\.invalid\)"
    assert plain("![x](https://e.invalid)") == shown


def test_plain_keeps_line_breaks():
    assert plain("a\nb") == "a  \nb"


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("case:u1", "`case:u1`"),
        ("u1` [x](y) `", "`` u1` [x](y) ` ``"),
        ("a``b", "```a``b```"),
        ("a\nb", "`a b`"),
    ],
)
def test_code_fence_outlasts_the_backticks_in_the_text(text, shown):
    assert code(text) == shown


def test_plain_breaks_bare_urls_hosts_and_email_addresses():
    # GFM links these without any Markdown syntax, and a backslash escape does
    # not stop it; the word joiner does (checked by rendering, hindcast.escape).
    from hindcast.escape import WORD_JOINER

    text = "See https://example.invalid/a, WWW.example.invalid, mailto:ops@example.invalid."
    shown = plain(text)

    assert re.search(f"(?<!{WORD_JOINER})[:@]", shown) is None
    assert f"https{WORD_JOINER}://" in shown
    assert f"WWW{WORD_JOINER}\\." in shown
    assert f"ops{WORD_JOINER}@" in shown
    # Without the joiners the text is the escaped text: nothing is dropped.
    assert shown.replace(WORD_JOINER, "") == text.translate(
        str.maketrans({c: f"\\{c}" for c in "\\`*_{}[]<>()#+-.!|~$"})
    )


def test_plain_escapes_a_setext_underline_and_an_entity():
    assert plain("Cause\n===") == "Cause  \n\\=\\=\\="
    assert plain("&lt;b&gt;") == "\\&lt;b\\&gt;"
