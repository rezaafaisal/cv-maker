"""Web app lokal CV Maker (Flask)."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_file, url_for)
from PIL import Image, ImageOps

from . import sections as S
from .db import DB
from .render import render_html, render_pdf

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CVMAKER_DATA", ROOT / "data"))
OUTPUT_DIR = Path(os.environ.get("CVMAKER_OUTPUT", ROOT / "output"))
PHOTO_DIR = DATA_DIR / "photos"
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
ACCENTS = ["#1f3a5f", "#17324d", "#0f5257", "#2d4a3e", "#5b2a3c", "#3b3b58", "#7a4b1d", "#333333"]


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates/ui", static_folder="static")
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024
    app.secret_key = "cv-maker-local"  # hanya untuk flash message; app berjalan lokal

    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    db = DB(DATA_DIR / "cv.db")

    # ------------------------------------------------------------ helpers
    def get_cv_or_404(cv_id: int) -> dict:
        cv = db.get(cv_id)
        if cv is None:
            abort(404)
        return cv

    def photo_path(cv: dict) -> Path | None:
        if not cv.get("photo"):
            return None
        p = PHOTO_DIR / cv["photo"]
        return p if p.exists() else None

    def clean_meta(src: dict, cur: dict) -> dict:
        out = {}
        if "name" in src:
            out["name"] = (src.get("name") or "").strip() or cur["name"]
        if src.get("template") in S.TEMPLATES:
            out["template"] = src["template"]
        if src.get("lang") in S.LANGS:
            out["lang"] = src["lang"]
        if HEX_COLOR.match(src.get("accent") or ""):
            out["accent"] = src["accent"]
        return out

    def save_photo(cv_id: int, raw: bytes) -> str:
        """Crop tengah jadi persegi, resize 600px, simpan JPEG."""
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
        img = ImageOps.fit(img.convert("RGB"), (600, 600), Image.LANCZOS, centering=(0.5, 0.4))
        name = f"{cv_id}.jpg"
        img.save(PHOTO_DIR / name, "JPEG", quality=88, optimize=True)
        return name

    def slug(text: str) -> str:
        text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE).strip()
        return re.sub(r"[\s_]+", "-", text) or "CV"

    def pdf_filename(cv: dict) -> str:
        person = cv["data"]["personal"].get("name") or cv["name"]
        return f"CV_{slug(person)}_{cv['template'].upper()}_{cv['lang'].upper()}.pdf"

    # ------------------------------------------------------------- pages
    @app.get("/")
    def index():
        return render_template("index.html", cvs=db.list_cvs())

    @app.post("/cv/new")
    def cv_new():
        name = (request.form.get("name") or "").strip() or "CV Baru"
        template = request.form.get("template") if request.form.get("template") in S.TEMPLATES else "ats"
        lang = request.form.get("lang") if request.form.get("lang") in S.LANGS else "id"
        data = S.new_cv_data()
        data["personal"]["name"] = (request.form.get("person") or "").strip()
        cv_id = db.create(name, template, lang, data=data)
        return redirect(url_for("editor", cv_id=cv_id))

    @app.get("/cv/<int:cv_id>")
    def editor(cv_id: int):
        cv = get_cv_or_404(cv_id)
        return render_template("editor.html", cv=cv, schema=S.editor_schema(), accents=ACCENTS,
                               has_photo=photo_path(cv) is not None,
                               versions=len(db.list_versions(cv_id)))

    @app.post("/api/cv/<int:cv_id>")
    def api_save(cv_id: int):
        cv = get_cv_or_404(cv_id)
        payload = request.get_json(silent=True) or {}
        fields = clean_meta(payload, cv)
        if isinstance(payload.get("data"), dict):
            fields["data"] = payload["data"]
        db.update(cv_id, **fields)
        return jsonify(ok=True, saved_at=datetime.now().strftime("%H:%M:%S"))

    @app.get("/cv/<int:cv_id>/preview")
    def preview(cv_id: int):
        cv = get_cv_or_404(cv_id)
        vid = request.args.get("version", type=int)
        if vid:
            v = db.get_version(cv_id, vid) or abort(404)
            cv = {**cv, **{k: v[k] for k in ("template", "lang", "accent", "data")}}
        return render_html(cv, photo_path(cv))

    @app.get("/cv/<int:cv_id>/preview.pdf")
    def preview_pdf(cv_id: int):
        """PDF asli untuk dicek (pemisahan halaman), tanpa membuat snapshot riwayat."""
        cv = get_cv_or_404(cv_id)
        return send_file(io.BytesIO(render_pdf(cv, photo_path(cv))), mimetype="application/pdf",
                         download_name=pdf_filename(cv))

    @app.get("/cv/<int:cv_id>/pdf")
    def pdf(cv_id: int):
        cv = get_cv_or_404(cv_id)
        pdf_bytes = render_pdf(cv, photo_path(cv))

        # Snapshot riwayat (skip bila isinya identik dengan versi terakhir).
        versions = db.list_versions(cv_id)
        last = db.get_version(cv_id, versions[0]["id"]) if versions else None
        if not last or any(last[k] != cv[k] for k in ("template", "lang", "accent", "data")):
            db.add_version(cv, note=request.args.get("note", ""))

        fname = pdf_filename(cv)
        (OUTPUT_DIR / fname).write_bytes(pdf_bytes)
        return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                         as_attachment=request.args.get("inline") != "1", download_name=fname)

    # ------------------------------------------------------------- photo
    @app.post("/cv/<int:cv_id>/photo")
    def photo_upload(cv_id: int):
        get_cv_or_404(cv_id)
        f = request.files.get("photo")
        if not f or not f.filename:
            return jsonify(ok=False, error="File foto kosong"), 400
        try:
            name = save_photo(cv_id, f.read())
        except Exception:  # noqa: BLE001 - file bukan gambar valid
            return jsonify(ok=False, error="File bukan gambar yang valid (pakai JPG/PNG)"), 400
        db.update(cv_id, photo=name)
        return jsonify(ok=True)

    @app.post("/cv/<int:cv_id>/photo/delete")
    def photo_delete(cv_id: int):
        cv = get_cv_or_404(cv_id)
        p = photo_path(cv)
        if p:
            p.unlink(missing_ok=True)
        db.update(cv_id, photo=None)
        return jsonify(ok=True)

    @app.get("/cv/<int:cv_id>/photo")
    def photo_get(cv_id: int):
        p = photo_path(get_cv_or_404(cv_id)) or abort(404)
        return send_file(p, mimetype="image/jpeg", max_age=0)

    # -------------------------------------------------- manage / history
    @app.post("/cv/<int:cv_id>/duplicate")
    def duplicate(cv_id: int):
        cv = get_cv_or_404(cv_id)
        new_id = db.create(f"{cv['name']} (salinan)", cv["template"], cv["lang"], cv["accent"], cv["data"])
        p = photo_path(cv)
        if p:
            shutil.copyfile(p, PHOTO_DIR / f"{new_id}.jpg")
            db.update(new_id, photo=f"{new_id}.jpg")
        flash(f"CV \"{cv['name']}\" diduplikat.")
        return redirect(url_for("editor", cv_id=new_id))

    @app.post("/cv/<int:cv_id>/delete")
    def delete(cv_id: int):
        cv = get_cv_or_404(cv_id)
        p = photo_path(cv)
        if p:
            p.unlink(missing_ok=True)
        db.delete(cv_id)
        flash(f"CV \"{cv['name']}\" dihapus.")
        return redirect(url_for("index"))

    @app.get("/cv/<int:cv_id>/versions")
    def versions(cv_id: int):
        cv = get_cv_or_404(cv_id)
        return render_template("versions.html", cv=cv, versions=db.list_versions(cv_id))

    @app.get("/cv/<int:cv_id>/versions/<int:vid>/pdf")
    def version_pdf(cv_id: int, vid: int):
        cv = get_cv_or_404(cv_id)
        v = db.get_version(cv_id, vid) or abort(404)
        cv = {**cv, **{k: v[k] for k in ("template", "lang", "accent", "data")}}
        fname = pdf_filename(cv).replace(".pdf", f"_v{vid}.pdf")
        return send_file(io.BytesIO(render_pdf(cv, photo_path(cv))), mimetype="application/pdf",
                         as_attachment=True, download_name=fname)

    @app.post("/cv/<int:cv_id>/versions/<int:vid>/restore")
    def version_restore(cv_id: int, vid: int):
        cv = get_cv_or_404(cv_id)
        v = db.get_version(cv_id, vid) or abort(404)
        db.add_version(cv, note=f"Otomatis: sebelum restore ke versi #{vid}")
        db.update(cv_id, template=v["template"], lang=v["lang"], accent=v["accent"], data=v["data"])
        flash(f"CV dipulihkan ke versi #{vid}. Versi sebelumnya disimpan di riwayat.")
        return redirect(url_for("editor", cv_id=cv_id))

    @app.post("/cv/<int:cv_id>/versions/<int:vid>/delete")
    def version_delete(cv_id: int, vid: int):
        get_cv_or_404(cv_id)
        db.delete_version(cv_id, vid)
        return redirect(url_for("versions", cv_id=cv_id))

    # ---------------------------------------------------- import / export
    @app.get("/cv/<int:cv_id>/export")
    def export(cv_id: int):
        cv = get_cv_or_404(cv_id)
        p = photo_path(cv)
        doc = {
            "cv_maker_export": 1,
            "name": cv["name"], "template": cv["template"], "lang": cv["lang"], "accent": cv["accent"],
            "photo_base64": base64.b64encode(p.read_bytes()).decode() if p else None,
            "data": cv["data"],
        }
        buf = io.BytesIO(json.dumps(doc, ensure_ascii=False, indent=2).encode())
        return send_file(buf, mimetype="application/json", as_attachment=True,
                         download_name=f"{slug(cv['name'])}.json")

    @app.post("/import")
    def import_json():
        f = request.files.get("file")
        try:
            doc = json.loads(f.read().decode("utf-8")) if f else None
            if not isinstance(doc, dict) or not isinstance(doc.get("data"), dict):
                raise ValueError
        except Exception:  # noqa: BLE001
            flash("File JSON tidak valid. Gunakan file hasil Export dari CV Maker.", "error")
            return redirect(url_for("index"))
        meta = clean_meta(doc, {"name": "CV Import"})
        cv_id = db.create(meta.get("name", "CV Import"), meta.get("template", "ats"),
                          meta.get("lang", "id"), meta.get("accent", "#1f3a5f"), doc["data"])
        if doc.get("photo_base64"):
            try:
                db.update(cv_id, photo=save_photo(cv_id, base64.b64decode(doc["photo_base64"])))
            except Exception:  # noqa: BLE001
                flash("Foto pada file import tidak valid, dilewati.", "error")
        flash("CV berhasil di-import.")
        return redirect(url_for("editor", cv_id=cv_id))

    return app
