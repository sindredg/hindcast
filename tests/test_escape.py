"""Model text shown on a page as written."""

import pytest

from hindcast.escape import code, plain


def test_plain_escapes_a_link_and_an_image():
    assert plain("![x](https://e.invalid)") == r"\!\[x\]\(https://e\.invalid\)"


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
