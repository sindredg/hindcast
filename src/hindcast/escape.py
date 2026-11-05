"""Model-written text shown on a Streamlit page as written, not as Markdown.

st.markdown, st.caption, expander labels, and st.table cells all render
Markdown, so a claim the model wrote can show an image or offer a link that a
planted instruction asked for. Both pages pass model text through here.
"""

import re

_MARKDOWN = str.maketrans({c: f"\\{c}" for c in "\\`*_{}[]<>()#+-.!|~$"})


def plain(text: object) -> str:
    """Text shown as written: Markdown characters escaped, line breaks kept."""
    return str(text).translate(_MARKDOWN).replace("\n", "  \n")


def code(text: object) -> str:
    """Text as an inline code span that a backtick in it cannot close.

    A backslash does not escape inside a code span, so the fence is one
    backtick longer than the longest run of backticks in the text (CommonMark).
    """
    text = str(text).replace("\n", " ")
    fence = "`" * (max((len(run) for run in re.findall("`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"
