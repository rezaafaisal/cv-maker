# CV Maker

Generator CV lokal: isi data lewat form web, pilih template, lalu download PDF yang rapi dan siap kirim.
Semua data tersimpan di SQLite, jadi CV bisa di-update dan di-generate ulang kapan saja.

- **2 template**
  - **ATS**: satu kolom, tanpa foto/ikon/tabel, sehingga teksnya terbaca bersih oleh sistem ATS.
  - **Modern**: sidebar berwarna, foto bulat, dan data diri.
- **Bahasa CV**: Indonesia / English. Judul section, nama bulan, dan "Sekarang/Present" otomatis berganti.
- **Section**: Ringkasan, Pengalaman Kerja, Proyek, Pendidikan, Keahlian, Sertifikasi, Organisasi,
  Penghargaan, Bahasa, Referensi, plus **section kustom** dengan judul bebas.
  Setiap section bisa disembunyikan, diurutkan ulang, dan diganti judulnya. Section yang kosong tidak ikut dicetak.
- **Info tambahan** di header (mis. Visa, Ketersediaan, SIM) dan **Data Diri** (khusus template Modern).
- **Autosave + live preview**, **riwayat versi** (snapshot otomatis setiap download PDF, bisa
  download ulang atau dipulihkan), **duplikat CV**, dan **import/export JSON** (foto ikut ter-export).

## Stack

Python 3.11 · Flask · SQLite (`sqlite3` bawaan) · WeasyPrint (HTML/CSS → PDF) · Pillow (crop foto).
Tanpa Node atau build step. Frontend memakai vanilla JS.

## Instalasi (sekali saja)

```bash
conda env create -f environment.yml      # membuat env "cv-maker" (Python 3.11)
```

## Menjalankan

```bash
conda activate cv-maker
python main.py                # buka http://127.0.0.1:5055 (browser terbuka otomatis)
python main.py --port 8000    # port lain
python main.py --no-browser
```

## Alur membuat CV baru

1. Di halaman utama → **Buat CV Baru**: isi nama, label (mis. `Budi - Lamaran Backend`), template, dan bahasa.
2. Di editor (kiri form, kanan preview):
   - **Pengaturan CV**: template, bahasa, warna aksen, foto.
   - **Data Utama**: nama, headline, kontak.
   - **Info Tambahan / Data Diri**: opsional.
   - **Section CV**: klik judul untuk membuka, lalu **+ Tambah entri**.
     - Tanggal: tulis `2024-04` (otomatis jadi "Apr 2024") atau tahun saja `2019`.
       Centang *Masih berlangsung* untuk "Sekarang/Present".
     - Poin-poin: **1 baris = 1 poin**.
3. Data tersimpan otomatis. Tekan `Cmd+S` untuk menyimpan sekarang.
4. **Preview PDF** untuk mengecek pemisahan halaman, lalu **Download PDF**.
   Salinan PDF juga disimpan ke folder `output/`.

Untuk teman lain atau lamaran lain: pakai **Duplikat** lalu ubah seperlunya, tidak perlu mengetik ulang.
Untuk mencoba cepat: **Import** file `examples/contoh-cv.json`.

## Lokasi data

| Path | Isi |
|---|---|
| `data/cv.db` | Database SQLite (tabel `cvs` + `cv_versions`) |
| `data/photos/` | Foto (sudah di-crop 600×600 JPEG) |
| `output/` | Salinan PDF yang di-download |

Backup cukup dengan menyalin folder `data/`, atau pakai **Export JSON** per CV.
Lokasi folder bisa diganti lewat env `CVMAKER_DATA` dan `CVMAKER_OUTPUT`.

## Struktur kode

```
main.py                     entry point (argparse + buka browser)
cvmaker/app.py              route Flask
cvmaker/db.py               skema & query SQLite
cvmaker/sections.py         definisi section, field, label ID/EN, format tanggal
cvmaker/render.py           data → HTML (Jinja) → PDF (WeasyPrint)
cvmaker/templates/cv/       template CV: ats.html, modern.html  ← ubah desain di sini
cvmaker/templates/ui/       halaman web app
cvmaker/static/             CSS & JS editor
```

**Menambah template baru**: buat `cvmaker/templates/cv/<nama>.html`
(variabel konteksnya bisa dilihat di `build_context` pada `render.py`), lalu tambahkan `<nama>` ke
`TEMPLATES` di `sections.py` dan ke tombol pilihan di `static/editor.js`.

**Menambah section bawaan baru**: tambahkan ke `SECTION_DEFS` dan `DEFAULT_ORDER` di `sections.py`.
