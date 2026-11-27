# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Tests for helpdocs.py: the hand-rolled Markdown->HTML renderer."""
import unittest
import helpdocs


class TestInline(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(helpdocs._slug("Hello World"), "hello-world")
        self.assertEqual(helpdocs._slug("A & B!"), "a-b")

    def test_escape_code_bold_link(self):
        self.assertEqual(helpdocs._inline("<b>"), "&lt;b&gt;")
        self.assertEqual(helpdocs._inline("`x`"), "<code>x</code>")
        self.assertEqual(helpdocs._inline("**x**"), "<strong>x</strong>")
        self.assertEqual(helpdocs._inline("[t](u)"), '<a href="u">t</a>')

    def test_html_entity_is_double_escaped(self):
        # Documents the bug we hit: a literal &rarr; becomes visible text, so
        # docs must use the real unicode char instead.
        self.assertEqual(helpdocs._inline("a &rarr; b"), "a &amp;rarr; b")

    def test_unicode_arrow_passes_through(self):
        self.assertEqual(helpdocs._inline("a → b"), "a → b")


class TestRender(unittest.TestCase):
    def test_heading(self):
        self.assertEqual(helpdocs.render("## Hi there"), "<h3 id='hi-there'>Hi there</h3>")

    def test_code_fence_escapes(self):
        out = helpdocs.render("```\n<x> & y\n```")
        self.assertIn("help-code", out)
        self.assertIn("&lt;x&gt; &amp; y", out)

    def test_bullets(self):
        self.assertEqual(helpdocs.render("- a\n- b"), "<ul><li>a</li><li>b</li></ul>")

    def test_ordered(self):
        self.assertEqual(helpdocs.render("1. a\n2. b"), "<ol><li>a</li><li>b</li></ol>")

    def test_paragraph(self):
        self.assertEqual(helpdocs.render("hello world"), "<p>hello world</p>")

    def test_table(self):
        out = helpdocs.render("| A | B |\n| --- | --- |\n| 1 | 2 |")
        self.assertIn("help-table", out)
        self.assertIn("<th>A</th>", out)
        self.assertIn("<td>1</td>", out)


if __name__ == "__main__":
    unittest.main()
