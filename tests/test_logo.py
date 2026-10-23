import re
import xml.etree.ElementTree as ET

from django.contrib.staticfiles import finders

SVG = "{http://www.w3.org/2000/svg}"


def test_logo_wordmark_is_large_enough_to_read():
    """The viewBox is 100 wide: the word must fill most of the circle (it was 16 units, ~7px in the header)."""
    root = ET.parse(finders.find("img/logo.svg")).getroot()
    text = root.find(f"{SVG}text")
    assert text.text == "REMESH" and text.get("fill") == "#fff" and root.find(f"{SVG}circle").get("fill") == "#000"
    assert float(text.get("font-size")) >= 20
    assert 80 <= float(text.get("textLength")) <= 90  # fixed width: the same fill whatever fallback font is used


def test_header_logo_is_rendered_big_enough(client):
    html = client.get("/").content.decode()
    img = re.search(r'<img src="[^"]*logo\.svg" alt="REMESH" width="(\d+)" height="(\d+)"', html)
    assert img and int(img.group(1)) >= 56 and img.group(1) == img.group(2)
