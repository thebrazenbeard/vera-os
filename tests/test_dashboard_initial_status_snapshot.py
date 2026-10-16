"""Initial browser paint must show genuine local resident state without JS polling."""
from pathlib import Path
import sys
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class ElementText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_status = False
        self.current = []
        self.status_text = ""
    def handle_starttag(self, name, attrs):
        if name == "p" and dict(attrs).get("id") == "status":
            self.in_status = True
    def handle_data(self, data):
        if self.in_status:
            self.current.append(data)
    def handle_endtag(self, name):
        if name == "p" and self.in_status:
            self.status_text = "".join(self.current)
            self.in_status = False


def test_snapshot_first_paint_is_truthful_and_needs_no_script():
    from veraos.desktop import render_dashboard
    state = {
        "status": "COMPOSED_NO_COGNITION",
        "components": ["vera_core", "portal", "pre_active", "volition"],
        "canonical_runtime_qualified": False,
        "cognition_route_qualified": False,
        "protected_effect_authority": False,
    }
    html = render_dashboard(state)
    parser = ElementText()
    parser.feed(html)
    assert parser.status_text == "COMPOSED_NO_COGNITION"
    assert "<li>vera_core</li>" in html
    assert "Canonical Vera runtime: <span id=\"canonical\" class=\"state\">UNQUALIFIED</span>" in html
    assert "Local cognition: <span id=\"cognition\" class=\"state\">NO ROUTE</span>" in html
    assert "<span id=\"effects\" class=\"state\">DENIED</span>" in html
    assert "<script" not in html.lower()
    assert "setInterval" not in html
    assert "status snapshot" in html.lower()
    assert "https://" not in html and "http://" not in html


def test_snapshot_escapes_untrusted_component_labels_and_status():
    from veraos.desktop import render_dashboard
    html = render_dashboard({
        "status": "<img src=x onerror=alert(1)>",
        "components": ["<svg onload=alert(1)>"],
        "protected_effect_authority": False,
    })
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&lt;svg onload=alert(1)&gt;" in html
    assert "<img src=x" not in html and "<svg onload" not in html
    assert "<script" not in html.lower()
