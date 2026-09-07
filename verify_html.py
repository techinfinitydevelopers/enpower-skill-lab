"""
Nesting check for rendered pages.

An edit to a base template left one extra `</div>`, which closed the sidebar
wrapper early and pushed a whole dashboard out of place. Nothing caught it:
the page still returned 200 and contained no leftover template syntax, so the
layout broke silently and only a screenshot revealed it. A second, older stray
`</div>` had been sitting in the Super Admin dashboard the whole time.

`problems_in(html)` returns a list of human-readable complaints, empty when the
markup nests correctly. Used by verify_pages on every page it already fetches.
"""

from html.parser import HTMLParser

# Tags that never take a closing tag.
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
        'meta', 'param', 'source', 'track', 'wbr'}

# Tags browsers legitimately auto-close. An unbalanced one of these is bad
# markup but not a layout bug, and flagging them would bury the real ones.
LENIENT = {'p', 'li', 'tr', 'td', 'th', 'option', 'thead', 'tbody', 'dt', 'dd'}


class _Nesting(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        pass  # self-closing, nothing to track

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.problems.append(f'</{tag}> at line {self.getpos()[0]} closes nothing')
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        while self.stack and self.stack[-1][0] in LENIENT:
            self.stack.pop()
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        elif tag not in LENIENT:
            open_tag, open_line = self.stack[-1]
            self.problems.append(
                f'</{tag}> at line {self.getpos()[0]} but <{open_tag}> from '
                f'line {open_line} is still open')


def problems_in(html):
    """Everything wrong with this page's nesting, most useful first."""
    found = []

    opens, closes = html.count('<div'), html.count('</div>')
    if opens != closes:
        found.append(f'{opens} <div> against {closes} </div>')

    parser = _Nesting()
    try:
        parser.feed(html)
    except Exception as e:
        found.append(f'could not be parsed: {type(e).__name__}: {e}')
        return found

    found.extend(parser.problems[:3])
    unclosed = [t for t in parser.stack if t[0] not in LENIENT]
    if unclosed:
        found.append('never closed: ' + ', '.join(
            f'<{t}> line {ln}' for t, ln in unclosed[:3]))
    return found
