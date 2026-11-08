"""Render CV (HTML -> PDF) memakai Jinja2 + WeasyPrint.

HTML yang sama dipakai untuk preview di browser dan untuk PDF, jadi apa yang
terlihat di preview = hasil PDF.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import sections as S

CV_TEMPLATE_DIR = Path(__file__).parent / "templates" / "cv"

_env = Environment(
    loader=FileSystemLoader(CV_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _has_content(section: dict) -> bool:
    if not section.get("enabled", True):
        return False
    if S.section_def(section)["kind"] == "text":
        return bool((section.get("text") or "").strip())
    return any(any(str(v).strip() for k, v in it.items() if k != "current" and v) for it in section.get("items", []))


def _bullets(text: str | None) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = re.sub(r"^\s*[-•*·]\s*", "", line).strip()
        if line:
            out.append(line)
    return out


def _paragraphs(text: str | None) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


def _pretty_url(url: str | None) -> str:
    return re.sub(r"^https?://(www\.)?", "", (url or "").strip()).rstrip("/")


def _href(url: str | None) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://", "mailto:")):
        return url
    return "https://" + url


def photo_data_uri(photo_path: Path | None) -> str | None:
    if not photo_path or not photo_path.exists():
        return None
    return "data:image/jpeg;base64," + base64.b64encode(photo_path.read_bytes()).decode()


def build_context(cv: dict, photo_path: Path | None = None) -> dict:
    lang = cv["lang"] if cv["lang"] in S.LANGS else "id"
    data = cv["data"]
    p = data["personal"]

    contacts = []  # (icon, text, href)
    if p.get("phone"):
        contacts.append(("phone", p["phone"], ""))
    if p.get("email"):
        contacts.append(("mail", p["email"], "mailto:" + p["email"].strip()))
    if p.get("location"):
        contacts.append(("pin", p["location"], ""))
    for key in ("linkedin", "github", "website"):
        if p.get(key):
            contacts.append(("link", _pretty_url(p[key]), _href(p[key])))

    secs = []
    for s in data["sections"]:
        if not _has_content(s):
            continue
        d = S.section_def(s)
        secs.append({
            "type": s["type"],
            "kind": d["kind"],
            "compact": d.get("compact", False),
            "inline": d.get("inline", False),
            "title": S.section_title(s, lang),
            "text": s.get("text", ""),
            "rows": [it for it in s.get("items", [])
                      if any(str(v).strip() for k, v in it.items() if k != "current" and v)],
        })

    details = [(lbl[lang], S.fmt_date(data["details"].get(k), lang))
               for k, lbl in S.DETAIL_FIELDS if (data["details"].get(k) or "").strip()]

    return {
        "lang": lang,
        "accent": cv.get("accent") or "#1f3a5f",
        "p": p,
        "contacts": contacts,
        "extra_info": [e for e in data.get("extra_info", []) if (e.get("value") or "").strip()],
        "details": details,
        "sections": secs,
        "photo": photo_data_uri(photo_path),
        "L": {k: v[lang] for k, v in S.LABELS.items()},
        "period": lambda it: S.fmt_range(it, lang),
        "date": lambda v: S.fmt_date(v, lang),
        "bullets": _bullets,
        "paragraphs": _paragraphs,
        "href": _href,
        "pretty_url": _pretty_url,
    }


def render_html(cv: dict, photo_path: Path | None = None) -> str:
    tpl = cv["template"] if cv["template"] in S.TEMPLATES else "ats"
    return _env.get_template(f"{tpl}.html").render(**build_context(cv, photo_path))


def render_pdf(cv: dict, photo_path: Path | None = None) -> bytes:
    from weasyprint import HTML  # import lambat; hanya saat dibutuhkan

    # Judul & author PDF diambil WeasyPrint dari <title> dan <meta name="author">.
    return HTML(string=render_html(cv, photo_path), base_url=str(CV_TEMPLATE_DIR)).write_pdf()
