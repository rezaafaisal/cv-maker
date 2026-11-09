"""Definisi section CV, label i18n (ID/EN), dan data default CV baru.

Semua isi CV disimpan sebagai satu dokumen JSON (lihat `new_cv_data`).
Struktur ini dipakai bersama oleh editor (JS), renderer (Jinja) dan DB.
"""

from __future__ import annotations

import copy
import re
import uuid

LANGS = ("id", "en", "ja")
TEMPLATES = ("ats", "modern")

# --------------------------------------------------------------------------
# Field yang tersedia untuk tipe "entries". Tiap section memilih subset field
# + label yang sesuai konteks (mis. title = "Posisi" di Pengalaman).
# --------------------------------------------------------------------------
# kind:
#   text    -> satu paragraf (Ringkasan)
#   entries -> daftar entri (judul, subjudul, lokasi, tanggal, poin-poin)
#   pairs   -> daftar label: nilai (Skill per kategori, Bahasa: level)
SECTION_DEFS: dict[str, dict] = {
    "summary": {
        "kind": "text",
        "title": {"id": "Ringkasan Profil", "en": "Professional Summary", "ja": "職務要約"},
    },
    "experience": {
        "kind": "entries",
        "title": {"id": "Pengalaman Kerja", "en": "Work Experience", "ja": "職務経歴"},
        "fields": {
            "title": "Posisi / Jabatan",
            "subtitle": "Perusahaan",
            "location": "Lokasi",
            "start": "Mulai",
            "end": "Selesai",
            "bullets": "Pencapaian / tanggung jawab (1 baris = 1 poin)",
        },
    },
    "education": {
        "kind": "entries",
        "title": {"id": "Pendidikan", "en": "Education", "ja": "学歴"},
        "fields": {
            "title": "Gelar / Jurusan",
            "subtitle": "Institusi / Sekolah",
            "location": "Lokasi",
            "meta": "IPK / Nilai (opsional)",
            "start": "Mulai",
            "end": "Lulus",
            "bullets": "Keterangan: skripsi, prestasi (1 baris = 1 poin)",
        },
    },
    "skills": {
        "kind": "pairs",
        "title": {"id": "Keahlian", "en": "Skills", "ja": "スキル"},
        "fields": {"label": "Kategori (opsional)", "value": "Daftar skill, pisahkan koma"},
    },
    "projects": {
        "kind": "entries",
        "title": {"id": "Proyek", "en": "Projects", "ja": "プロジェクト"},
        "fields": {
            "title": "Nama Proyek",
            "subtitle": "Peran",
            "meta": "Teknologi / tools",
            "link": "Link (opsional)",
            "start": "Mulai",
            "end": "Selesai",
            "bullets": "Deskripsi (1 baris = 1 poin)",
        },
    },
    "certifications": {
        "kind": "entries",
        "compact": True,
        "title": {"id": "Sertifikasi", "en": "Certifications", "ja": "資格・認定"},
        "fields": {
            "title": "Nama Sertifikat",
            "subtitle": "Penerbit",
            "meta": "ID / No. Kredensial (opsional)",
            "link": "Link (opsional)",
            "end": "Tanggal / Tahun",
        },
    },
    "languages": {
        "kind": "pairs",
        "inline": True,
        "title": {"id": "Bahasa", "en": "Languages", "ja": "語学"},
        "fields": {"label": "Bahasa", "value": "Tingkat (mis. Native, B2, Aktif)"},
    },
    "organizations": {
        "kind": "entries",
        "title": {"id": "Pengalaman Organisasi", "en": "Organizational Experience", "ja": "団体・組織での活動"},
        "fields": {
            "title": "Peran / Jabatan",
            "subtitle": "Organisasi",
            "location": "Lokasi",
            "start": "Mulai",
            "end": "Selesai",
            "bullets": "Kegiatan (1 baris = 1 poin)",
        },
    },
    "awards": {
        "kind": "entries",
        "compact": True,
        "title": {"id": "Penghargaan", "en": "Awards", "ja": "受賞歴"},
        "fields": {
            "title": "Nama Penghargaan",
            "subtitle": "Pemberi",
            "end": "Tanggal / Tahun",
            "bullets": "Keterangan (opsional)",
        },
    },
    "references": {
        "kind": "entries",
        "compact": True,
        "title": {"id": "Referensi", "en": "References", "ja": "推薦者"},
        "fields": {
            "title": "Nama",
            "subtitle": "Jabatan & Perusahaan",
            "meta": "Kontak (telp / email)",
        },
    },
}

CUSTOM_DEF = {
    "kind": "entries",
    "title": {"id": "Section Kustom", "en": "Custom Section", "ja": "その他"},
    "fields": {
        "title": "Judul",
        "subtitle": "Subjudul",
        "location": "Lokasi",
        "meta": "Info tambahan",
        "link": "Link",
        "start": "Mulai",
        "end": "Selesai",
        "bullets": "Poin-poin (1 baris = 1 poin)",
    },
}

DEFAULT_ORDER = [
    "summary", "experience", "projects", "education", "skills",
    "certifications", "organizations", "awards", "languages", "references",
]

# Data pribadi gaya Indonesia: hanya tampil di template Modern.
DETAIL_FIELDS = [
    ("birth_place", {"id": "Tempat Lahir", "en": "Place of Birth", "ja": "出身地"}),
    ("birth_date", {"id": "Tanggal Lahir", "en": "Date of Birth", "ja": "生年月日"}),
    ("gender", {"id": "Jenis Kelamin", "en": "Gender", "ja": "性別"}),
    ("marital_status", {"id": "Status", "en": "Marital Status", "ja": "婚姻状況"}),
    ("religion", {"id": "Agama", "en": "Religion", "ja": "宗教"}),
    ("nationality", {"id": "Kewarganegaraan", "en": "Nationality", "ja": "国籍"}),
    ("height_weight", {"id": "Tinggi / Berat", "en": "Height / Weight", "ja": "身長・体重"}),
]

LABELS = {
    "present": {"id": "Sekarang", "en": "Present", "ja": "現在"},
    "contact": {"id": "Kontak", "en": "Contact", "ja": "連絡先"},
    "personal_details": {"id": "Data Diri", "en": "Personal Details", "ja": "個人情報"},
    "full_name": {"id": "Nama Lengkap", "en": "Full Name", "ja": "氏名"},
    "cv_title": {"id": "Curriculum Vitae", "en": "Curriculum Vitae", "ja": "職務経歴書"},
}

MONTHS = {
    "id": ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"],
    "ja": [f"{i}月" for i in range(1, 13)],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
MONTHS_LONG = {
    "ja": [f"{i}月" for i in range(1, 13)],
    "id": ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
           "Agustus", "September", "Oktober", "November", "Desember"],
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
}

_YM = re.compile(r"^\s*(\d{4})-(\d{1,2})\s*$")
_YMD = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$")


def fmt_date(value: str | None, lang: str) -> str:
    """'2024-04' -> 'Apr 2024'; '2000-08-24' -> '24 Agustus 2000'; lainnya apa adanya."""
    if not value:
        return ""
    m = _YMD.match(value)
    if m and 1 <= int(m.group(2)) <= 12:
        if lang == "ja":
            return f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日"
        return f"{int(m.group(3))} {MONTHS_LONG[lang][int(m.group(2)) - 1]} {m.group(1)}"
    m = _YM.match(value)
    if m and 1 <= int(m.group(2)) <= 12:
        if lang == "ja":
            return f"{m.group(1)}年{int(m.group(2))}月"
        return f"{MONTHS[lang][int(m.group(2)) - 1]} {m.group(1)}"
    if lang == "ja" and re.fullmatch(r"\d{4}", value.strip()):
        return f"{value.strip()}年"
    return value.strip()


def fmt_range(item: dict, lang: str) -> str:
    start = fmt_date(item.get("start"), lang)
    end = LABELS["present"][lang] if item.get("current") else fmt_date(item.get("end"), lang)
    if start and end:
        return f"{start} 〜 {end}" if lang == "ja" else f"{start} – {end}"
    return start or end


def section_def(section: dict) -> dict:
    return SECTION_DEFS.get(section.get("type"), CUSTOM_DEF)


def section_title(section: dict, lang: str) -> str:
    if (section.get("title") or "").strip():
        return section["title"].strip()
    return section_def(section)["title"][lang]


def _sid() -> str:
    return uuid.uuid4().hex[:8]


def new_section(stype: str) -> dict:
    d = SECTION_DEFS.get(stype, CUSTOM_DEF)
    sec = {"id": _sid(), "type": stype if stype in SECTION_DEFS else "custom",
           "title": "", "enabled": True}
    if d["kind"] == "text":
        sec["text"] = ""
    else:
        sec["items"] = []
    return sec


def new_cv_data() -> dict:
    return {
        "personal": {
            "name": "", "headline": "", "email": "", "phone": "", "location": "",
            "linkedin": "", "website": "", "github": "",
        },
        # Baris info tambahan bebas di header (mis. Visa, Ketersediaan, SIM).
        "extra_info": [],
        "details": {k: "" for k, _ in DETAIL_FIELDS},
        "sections": [new_section(t) for t in DEFAULT_ORDER],
    }


def normalize(data: dict) -> dict:
    """Pastikan dokumen punya semua key yang dibutuhkan (untuk data lama / import)."""
    base = new_cv_data()
    out = copy.deepcopy(data) if isinstance(data, dict) else {}
    out.setdefault("personal", {})
    for k, v in base["personal"].items():
        out["personal"].setdefault(k, v)
    out.setdefault("details", {})
    for k, v in base["details"].items():
        out["details"].setdefault(k, v)
    out.setdefault("extra_info", [])
    if not isinstance(out.get("sections"), list):
        out["sections"] = base["sections"]
    for s in out["sections"]:
        s.setdefault("id", _sid())
        s.setdefault("type", "custom")
        s.setdefault("title", "")
        s.setdefault("enabled", True)
        if section_def(s)["kind"] == "text":
            s.setdefault("text", "")
        else:
            s.setdefault("items", [])
    return out


def editor_schema() -> dict:
    """Skema yang dikirim ke editor JS."""
    return {
        "sections": {k: {"kind": v["kind"], "title": v["title"], "fields": v.get("fields", {})}
                     for k, v in SECTION_DEFS.items()},
        "custom": {"kind": "entries", "title": CUSTOM_DEF["title"], "fields": CUSTOM_DEF["fields"]},
        "details": [{"key": k, "label": lbl["id"]} for k, lbl in DETAIL_FIELDS],
    }
