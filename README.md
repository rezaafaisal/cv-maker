# CV Maker

A local CV generator: fill in your data through a web form, pick a template, and download a clean,
ready-to-send PDF. Everything is stored in SQLite, so a CV can be updated and regenerated at any time.

- **2 templates**
  - **ATS**: single column, no photo, icons, or tables, so the text is read cleanly by applicant tracking systems.
  - **Modern**: colored sidebar, round photo, and personal details.
- **CV language**: Indonesian / English / Japanese (日本語). Section titles, date formats (e.g. `2024年4月 〜 現在`),
  and labels switch automatically. Japanese fonts are embedded in the PDF and the text stays selectable, so it scans cleanly in ATS.
- **Sections**: Summary, Work Experience, Projects, Education, Skills, Certifications, Organizations,
  Awards, Languages, References, plus **custom sections** with any title.
  Every section can be hidden, reordered, and renamed. Empty sections are not printed.
- **Extra info** in the header (e.g. Visa, Availability, Driver's license) and **Personal Details**
  (Modern template only).
- **Autosave + live preview**, **version history** (an automatic snapshot on every PDF download that
  can be re-downloaded or restored), **duplicate CV**, and **JSON import/export** (the photo is exported too).

> The web UI itself is in Indonesian. Button and field names below are given as they appear in the UI,
> with an English gloss.

## Stack

Python 3.11 · Flask · SQLite (built-in `sqlite3`) · WeasyPrint (HTML/CSS → PDF) · Pillow (photo cropping).
No Node and no build step. The frontend is vanilla JS.

## Installation (one time)

```bash
conda env create -f environment.yml      # creates the "cv-maker" env (Python 3.11)
```

## Running

```bash
conda activate cv-maker
python main.py                # opens http://127.0.0.1:5055 (browser opens automatically)
python main.py --port 8000    # different port
python main.py --no-browser
```

Restart the server after pulling code changes. (Templates reload automatically, but Python code does not.)

## Creating a new CV

1. On the home page, use **Buat CV Baru** (Create New CV): enter the name, a label (e.g. `Budi - Backend Application`),
   the template, and the language.
2. In the editor (form on the left, preview on the right):
   - **Pengaturan CV** (CV settings): template, language, accent color, photo.
   - **Data Utama** (main data): name, headline, contacts.
   - **Info Tambahan** (extra info) / **Data Diri** (personal details): optional.
   - **Section CV**: click a title to open it, then **+ Tambah entri** (add entry).
     - Dates: write `2024-04` (rendered as "Apr 2024") or just a year such as `2019`.
       Tick *Masih berlangsung* (still ongoing) to show "Sekarang/Present".
     - Bullet points: **1 line = 1 bullet**.
3. Data is saved automatically. Press `Cmd+S` to save immediately.
4. Use **Preview PDF** to check the page breaks, then **Download PDF**.
   A copy of the PDF is also saved to the `output/` folder.
5. **Simpan & CV Baru** (Save & New CV) saves the current CV and jumps straight to the new-CV form.

For another friend or another job application: use **Duplikat** (Duplicate) and adjust what you need, with no retyping.
To try it out quickly: **Import** `examples/contoh-cv.json` (Indonesian) or `examples/contoh-cv-ja.json` (Japanese).

## Data locations

| Path | Contents |
|---|---|
| `data/cv.db` | SQLite database (tables `cvs` + `cv_versions`) |
| `data/photos/` | Photos (already cropped to 600×600 JPEG) |
| `output/` | Copies of downloaded PDFs |

To back up, copy the `data/` folder, or use **Export JSON** on each CV.
The folder locations can be changed with the `CVMAKER_DATA` and `CVMAKER_OUTPUT` environment variables.

## Code structure

```
main.py                     entry point (argparse + opens the browser)
cvmaker/app.py              Flask routes
cvmaker/db.py               SQLite schema & queries
cvmaker/sections.py         section/field definitions, ID/EN labels, date formatting
cvmaker/render.py           data → HTML (Jinja) → PDF (WeasyPrint)
cvmaker/templates/cv/       CV templates: ats.html, modern.html  ← edit the design here
cvmaker/templates/ui/       web app pages
cvmaker/static/             editor CSS & JS
```

**Adding a new template**: create `cvmaker/templates/cv/<name>.html`
(the context variables are listed in `build_context` in `render.py`), then add `<name>` to
`TEMPLATES` in `sections.py` and to the selector buttons in `static/editor.js`.

**Adding a new built-in section**: add it to `SECTION_DEFS` and `DEFAULT_ORDER` in `sections.py`.

**PDF viewer note**: some mobile PDF viewers render CSS gradients and page backgrounds incorrectly.
The Modern template therefore draws its sidebar as a solid fixed box instead. Keep that approach if you edit the design.
