"""Text processing utilities: BBCode to HTML conversion."""
from __future__ import annotations

import html
import re


from PySide6.QtGui import QFont


def bbcode_to_html(input_text: str) -> str:
    text = html.escape(input_text)
    text = re.sub(r"\[b\](.*?)\[/b\]", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"\[i\](.*?)\[/i\]", r"<i>\1</i>", text, flags=re.DOTALL)
    text = re.sub(r"\[u\](.*?)\[/u\]", r"<u>\1</u>", text, flags=re.DOTALL)
    text = re.sub(r"\[h1\](.*?)\[/h1\]", r"<h1>\1</h1>", text, flags=re.DOTALL)
    text = re.sub(r"\[h2\](.*?)\[/h2\]", r"<h2>\1</h2>", text, flags=re.DOTALL)
    text = re.sub(r"\[h3\](.*?)\[/h3\]", r"<h3>\1</h3>", text, flags=re.DOTALL)
    text = re.sub(
        r"\[url=([^\]]+)\](.*?)\[/url\]", r'<a href="\1">\2</a>', text, flags=re.DOTALL
    )
    text = re.sub(
        r"\[url\](.*?)\[/url\]", r'<a href="\1">\1</a>', text, flags=re.DOTALL
    )
    text = re.sub(r"\[img\](.*?)\[/img\]", r'<img src="\1">', text, flags=re.DOTALL)
    text = re.sub(r"\[list\]", "<ul>", text)
    text = re.sub(r"\[/list\]", "</ul>", text)
    text = re.sub(r"\[\*\]", "<li>", text)
    text = text.replace("\n", "<br>")
    font = QFont()
    pt = font.pointSize()
    if pt > 0:
        font_size = f"{pt}pt"
    else:
        px = font.pixelSize()
        font_size = f"{px}px" if px > 0 else "medium"
    return f"<html><body style='font-size: {font_size};'>{text}</body></html>"
