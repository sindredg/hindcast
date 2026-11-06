"""Model-written text shown on a Streamlit page as written, not as Markdown.

st.markdown, st.caption, expander labels, and st.table cells all render
Markdown, so a claim the model wrote can show an image or offer a link that a
planted instruction asked for. Both pages pass model text through here.
"""

import re

# "=" would make a setext heading of the line above, and "&" starts an entity.
_MARKDOWN = str.maketrans({c: f"\\{c}" for c in "\\`*_{}[]<>()#+-.!|~$=&"})
# GitHub-flavoured Markdown also links a bare URL, a "www." host, and an
# e-mail address, and a backslash escape does not stop it: rendered in
# Streamlit 1.67.0, "https\://x", "ops\@x", and "www\.x" all became links.
# An invisible WORD JOINER before each ":" and "@" and after "www" did not.
WORD_JOINER = "\u2060"
_LINK_MARKS = re.compile(r"(?=[:@])")
_WWW = re.compile(r"(?i)(www)(?=\\\.)")


def plain(text: object) -> str:
    """Text shown as written: Markdown characters escaped, line breaks kept, no links."""
    text = str(text).translate(_MARKDOWN)
    text = _WWW.sub(lambda m: m.group(1) + WORD_JOINER, _LINK_MARKS.sub(WORD_JOINER, text))
    return text.replace("\n", "  \n")


def code(text: object) -> str:
    """Text as an inline code span that a backtick in it cannot close.

    A backslash does not escape inside a code span, so the fence is one
    backtick longer than the longest run of backticks in the text (CommonMark).
    """
    text = str(text).replace("\n", " ")
    fence = "`" * (max((len(run) for run in re.findall("`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"
