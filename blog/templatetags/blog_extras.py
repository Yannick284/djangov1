import re

import markdown as md
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "del", "a", "code", "pre",
    "blockquote", "img", "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}, "img": {"src", "alt", "title"}, "code": {"class"}}


_HEADING = re.compile(r"<(/?)h([1-6])\b")


def _demote_headings(html: str) -> str:
    """# → h2, ## → h3, ### et plus → h4 : le titre de la page reste l'unique h1."""
    return _HEADING.sub(lambda m: f"<{m.group(1)}h{min(int(m.group(2)) + 1, 4)}", html)


def render_markdown(text: str) -> str:
    """Markdown → HTML nettoyé (aucun script, aucune balise dangereuse)."""
    html = md.markdown(
        text or "",
        extensions=["extra", "nl2br", "sane_lists", "fenced_code"],
        output_format="html",
    )
    html = _demote_headings(html)
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
    )


@register.filter(name="markdown")
def markdown_filter(text):
    return mark_safe(render_markdown(text))
