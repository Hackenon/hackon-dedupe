# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Render the Markdown help docs to HTML for the in-app Help page.

No third-party dependency (the app's venv only has Flask/Pillow/ImageHash), so
this is a small hand-rolled converter for the subset used by docs/HELP.md and
docs/INSTALL.md: headings, paragraphs, bullet/numbered lists, fenced code,
inline code/bold/links, and pipe tables.
"""

import html
import re
from pathlib import Path
import paths

DOCS = paths.bundled("docs")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _inline(text):
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def render(md):
    lines = md.split("\n")
    out, i, n = [], 0, len(md.split("\n"))
    while i < n:
        line = lines[i]
        if line.startswith("```"):
            i += 1
            code = []
            while i < n and not lines[i].startswith("```"):
                code.append(html.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre class='help-code'>" + "\n".join(code) + "</pre>")
            continue
        heading = re.match(r"(#{1,4})\s+(.*)", line)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2)
            tag = "h" + str(min(level + 1, 5))
            out.append("<%s id='%s'>%s</%s>" % (tag, _slug(text), _inline(text), tag))
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < n and re.match(r"^\s*\|[-:\s|]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            parts = ["<table class='help-table'><thead><tr>"]
            parts += ["<th>%s</th>" % _inline(c) for c in header]
            parts.append("</tr></thead><tbody>")
            for row in rows:
                parts.append("<tr>" + "".join("<td>%s</td>" % _inline(c) for c in row) + "</tr>")
            parts.append("</tbody></table>")
            out.append("".join(parts))
            continue
        if re.match(r"\s*[-*]\s+", line):
            items = []
            while i < n and re.match(r"\s*[-*]\s+", lines[i]):
                items.append("<li>" + _inline(re.sub(r"\s*[-*]\s+", "", lines[i], count=1)) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r"\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"\s*\d+\.\s+", lines[i]):
                items.append("<li>" + _inline(re.sub(r"\s*\d+\.\s+", "", lines[i], count=1)) + "</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        if line.strip() == "":
            i += 1
            continue
        para = [line]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"(#{1,4})\s|```|\s*[-*]\s|\s*\d+\.\s|\s*\|", lines[i]):
            para.append(lines[i])
            i += 1
        out.append("<p>" + _inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def load(name):
    """Rendered HTML for a doc file, or a friendly message if it's missing."""
    path = DOCS / name
    if not path.exists():
        return "<p class='meta'>Guide file %s not found.</p>" % html.escape(name)
    return render(path.read_text(encoding="utf-8"))


def contents(name):
    """(title, anchor) for each top-level section (## heading), for a table of contents."""
    path = DOCS / name
    if not path.exists():
        return []
    found = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"##\s+(.*)", line)
        if m:
            found.append((m.group(1), _slug(m.group(1))))
    return found
