/* CV Maker – editor form dinamis (vanilla JS, tanpa build step).
 * State = window.CV (dokumen JSON). Setiap perubahan → autosave (debounce) → preview di-reload.
 */
(() => {
  "use strict";
  const cv = window.CV;
  const D = cv.data;
  const SCHEMA = window.SCHEMA;
  const URLS = window.URLS;
  const formEl = document.getElementById("form");
  const statusEl = document.getElementById("save-status");
  const iframe = document.getElementById("preview");
  const openSections = new Set();
  let hasPhoto = window.HAS_PHOTO;

  // ------------------------------------------------------------ helpers
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "class") el.className = v;
      else if (k === "value") el.value = v;
      else if (k === "checked") el.checked = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat()) {
      if (c == null || c === false) continue;
      el.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return el;
  }

  function field(obj, key, opts = {}) {
    const { label, type = "text", placeholder = "", rows, hint, cls = "", disabled } = opts;
    const onInput = (e) => { obj[key] = e.target.value; opts.onInput && opts.onInput(e); changed(); };
    const ctrl = rows
      ? h("textarea", { rows, placeholder, oninput: onInput })
      : h("input", { type, placeholder, oninput: onInput, disabled });
    ctrl.value = obj[key] ?? "";
    return h("label", { class: "field " + cls }, h("span", { class: "lbl" }, label), ctrl,
      hint ? h("small", { class: "hint" }, hint) : null);
  }

  const iconBtn = (text, title, onclick, cls = "") =>
    h("button", { type: "button", class: "icon " + cls, title, onclick }, text);

  function move(arr, i, d) {
    const j = i + d;
    if (j < 0 || j >= arr.length) return;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    structural();
  }
  function remove(arr, i, msg) {
    if (msg && !confirm(msg)) return;
    arr.splice(i, 1);
    structural();
  }
  const defOf = (s) => SCHEMA.sections[s.type] || SCHEMA.custom;
  const titleOf = (s) => (s.title || "").trim() || defOf(s).title[cv.lang];

  // ------------------------------------------------------- save/preview
  let timer = null, inflight = null, dirty = false;

  function changed() {
    dirty = true;
    statusEl.textContent = "Belum tersimpan…";
    statusEl.className = "small warn";
    clearTimeout(timer);
    timer = setTimeout(save, 700);
  }
  function structural() { render(); changed(); }

  async function save() {
    clearTimeout(timer);
    if (inflight) { await inflight; if (!dirty) return; }
    dirty = false;
    statusEl.textContent = "Menyimpan…";
    inflight = fetch(URLS.save, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: cv.name, template: cv.template, lang: cv.lang, accent: cv.accent, data: D }),
    }).then(async (r) => {
      if (!r.ok) throw new Error(r.status);
      const j = await r.json();
      statusEl.textContent = "Tersimpan " + j.saved_at;
      statusEl.className = "small ok";
      reloadPreview();
    }).catch((e) => {
      dirty = true;
      statusEl.textContent = "Gagal menyimpan (" + e.message + ") – apakah server masih jalan?";
      statusEl.className = "small err";
    }).finally(() => { inflight = null; });
    await inflight;
  }

  function reloadPreview() { iframe.src = URLS.preview + "?t=" + Date.now(); }

  // Ukuran & zoom preview: iframe dibuat setinggi kontennya, lalu di-scale.
  const PAGE_W = 840;
  let zoom = null;
  function fitPreview() {
    const wrap = iframe.parentElement;
    if (zoom == null) zoom = Math.min(1, (wrap.clientWidth - 24) / PAGE_W);
    let hgt = 1200;
    try { hgt = iframe.contentDocument.documentElement.scrollHeight; } catch (_) { /* ignore */ }
    iframe.style.width = PAGE_W + "px";
    iframe.style.height = hgt + "px";
    iframe.style.transform = `scale(${zoom})`;
    iframe.parentElement.style.setProperty("--ph", hgt * zoom + "px");
  }
  iframe.addEventListener("load", fitPreview);
  window.addEventListener("resize", () => { zoom = null; fitPreview(); });
  document.querySelectorAll("[data-zoom]").forEach((b) => b.addEventListener("click", () => {
    zoom = Math.max(0.3, Math.min(1.6, (zoom || 1) + 0.1 * Number(b.dataset.zoom)));
    fitPreview();
  }));

  // Pastikan data tersimpan sebelum generate PDF.
  for (const id of ["btn-pdf", "btn-preview-pdf"]) {
    const a = document.getElementById(id);
    a.addEventListener("click", async (e) => {
      if (!dirty && !inflight) return;
      e.preventDefault();
      await save();
      if (a.target === "_blank") window.open(a.href, "_blank"); else location.href = a.href;
    });
  }
  // Simpan & Keluar: pastikan tersimpan dulu, baru kembali ke daftar CV.
  document.getElementById("btn-exit").addEventListener("click", async (e) => {
    e.preventDefault();
    const href = e.currentTarget.href;
    await save();
    if (dirty) { alert("Gagal menyimpan, tidak pindah agar data tidak hilang."); return; }
    location.href = href;
  });
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
  });
  window.addEventListener("beforeunload", (e) => { if (dirty || inflight) { save(); e.preventDefault(); } });

  // ----------------------------------------------------------- sections
  function card(title, body, opts = {}) {
    return h("section", { class: "card " + (opts.cls || "") },
      h("div", { class: "card-head" }, h("h3", {}, title), opts.right || null),
      opts.note ? h("p", { class: "note" }, opts.note) : null,
      body);
  }

  function segmented(options, current, onPick) {
    return h("div", { class: "seg" }, options.map(([val, label]) =>
      h("button", { type: "button", class: val === current ? "on" : "", onclick: () => onPick(val) }, label)));
  }

  function renderSettings() {
    const swatches = h("div", { class: "swatches" },
      window.ACCENTS.map((c) => h("button", {
        type: "button", class: "sw" + (c === cv.accent ? " on" : ""), style: `background:${c}`, title: c,
        onclick: () => { cv.accent = c; structural(); },
      })),
      h("input", { type: "color", value: cv.accent, title: "Warna lain",
        onchange: (e) => { cv.accent = e.target.value; structural(); } }));

    const photoBox = h("div", { class: "photo-box" },
      hasPhoto ? h("img", { src: URLS.photo + "?t=" + Date.now(), alt: "foto" }) : h("div", { class: "ph" }, "Belum ada foto"),
      h("div", { class: "stack-sm" },
        h("input", { type: "file", accept: "image/*", onchange: uploadPhoto }),
        hasPhoto ? h("button", { type: "button", class: "btn sm danger", onclick: deletePhoto }, "Hapus foto") : null,
        h("small", { class: "hint" }, "Otomatis di-crop persegi (fokus bagian tengah-atas). Hanya tampil di template Modern.")));

    return card("Pengaturan CV", h("div", { class: "stack" },
      field(cv, "name", { label: "Label CV (internal)", hint: "Hanya untuk daftar CV, tidak tercetak." }),
      h("div", { class: "row-2" },
        h("div", { class: "field" }, h("span", { class: "lbl" }, "Template"),
          segmented([["ats", "ATS (tanpa foto)"], ["modern", "Modern (foto)"]], cv.template,
            (v) => { cv.template = v; structural(); })),
        h("div", { class: "field" }, h("span", { class: "lbl" }, "Bahasa CV"),
          segmented([["id", "Indonesia"], ["en", "English"]], cv.lang, (v) => { cv.lang = v; structural(); }))),
      h("div", { class: "field" }, h("span", { class: "lbl" }, "Warna aksen"), swatches),
      h("div", { class: "field" }, h("span", { class: "lbl" }, "Foto"), photoBox),
    ));
  }

  async function uploadPhoto(e) {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("photo", f);
    statusEl.textContent = "Mengunggah foto…";
    const r = await fetch(URLS.photoUpload, { method: "POST", body: fd });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { alert(j.error || "Upload gagal"); statusEl.textContent = ""; return; }
    hasPhoto = true;
    if (cv.template !== "modern" && confirm("Foto tersimpan. Ganti ke template Modern agar foto tampil?")) {
      cv.template = "modern"; structural(); return;
    }
    statusEl.textContent = "Foto tersimpan";
    render(); reloadPreview();
  }
  async function deletePhoto() {
    if (!confirm("Hapus foto?")) return;
    await fetch(URLS.photoDelete, { method: "POST" });
    hasPhoto = false; render(); reloadPreview();
  }

  function renderPersonal() {
    const P = D.personal;
    return card("Data Utama", h("div", { class: "grid" },
      field(P, "name", { label: "Nama lengkap *", cls: "span-2" }),
      field(P, "headline", { label: "Headline / posisi yang dilamar", cls: "span-2",
        placeholder: "mis. Full-Stack Developer | Web · AI" }),
      field(P, "email", { label: "Email", type: "email" }),
      field(P, "phone", { label: "No. HP / WhatsApp" }),
      field(P, "location", { label: "Domisili", cls: "span-2", placeholder: "mis. Makassar, Sulawesi Selatan" }),
      field(P, "linkedin", { label: "LinkedIn", placeholder: "linkedin.com/in/username" }),
      field(P, "github", { label: "GitHub / Portfolio", placeholder: "github.com/username" }),
      field(P, "website", { label: "Website", cls: "span-2" }),
    ));
  }

  function renderExtra() {
    const list = D.extra_info;
    const rows = list.map((it, i) => h("div", { class: "pair-row" },
      field(it, "label", { label: "Label", placeholder: "mis. Visa" }),
      field(it, "value", { label: "Isi", placeholder: "mis. Engineer, berlaku s/d Mei 2029" }),
      h("div", { class: "row-tools" },
        iconBtn("↑", "Naik", () => move(list, i, -1)), iconBtn("↓", "Turun", () => move(list, i, 1)),
        iconBtn("✕", "Hapus", () => remove(list, i), "del"))));
    return card("Info Tambahan (opsional)", h("div", { class: "stack" }, rows,
      h("button", { type: "button", class: "btn sm", onclick: () => { list.push({ label: "", value: "" }); structural(); } },
        "+ Tambah info")),
    { note: "Baris bebas di header CV, mis. Visa, Ketersediaan, SIM, Bersedia relokasi." });
  }

  function renderDetails() {
    return card("Data Diri (opsional)", h("div", { class: "grid" },
      SCHEMA.details.map((d) => field(D.details, d.key, {
        label: d.label,
        type: d.key === "birth_date" ? "date" : "text",
        placeholder: { gender: "Laki-laki / Perempuan", marital_status: "Belum Kawin / Kawin",
          height_weight: "mis. 170 cm / 65 kg" }[d.key] || "",
      }))),
    { note: "Hanya tampil di template Modern. Template ATS sengaja tidak memuat data pribadi (standar ATS/internasional)." });
  }

  const DATE_HINT = "Format: 2024-04 → otomatis jadi “Apr 2024”. Boleh juga tahun saja (2019) atau teks bebas.";

  function renderEntries(sec) {
    const fields = defOf(sec).fields;
    const items = sec.items;
    const order = ["title", "subtitle", "location", "meta", "link", "start", "end"];
    const list = items.map((it, i) => {
      const head = h("b", {}, it.title || it.subtitle || `Entri ${i + 1}`);
      const endInput = fields.end ? field(it, "end", { label: fields.end, placeholder: "2025-02",
        disabled: !!it.current }) : null;
      const els = order.filter((k) => fields[k]).map((k) => {
        if (k === "end") return endInput;
        return field(it, k, {
          label: fields[k],
          placeholder: k === "start" ? "2023-03" : "",
          onInput: (k === "title" || k === "subtitle") ? () => { head.textContent = it.title || it.subtitle || `Entri ${i + 1}`; } : null,
        });
      });
      if (fields.start && fields.end) {
        els.push(h("label", { class: "check span-2" },
          h("input", { type: "checkbox", checked: !!it.current, onchange: (e) => {
            it.current = e.target.checked;
            endInput.querySelector("input").disabled = it.current;
            changed();
          } }),
          " Masih berlangsung (tampil sebagai “Sekarang/Present”)"));
      }
      if (fields.bullets) els.push(field(it, "bullets", { label: fields.bullets, rows: 4, cls: "span-2",
        placeholder: "Tulis 1 poin per baris. Awali dengan kata kerja & angka hasil, mis:\nMeningkatkan penjualan 20% dalam 6 bulan." }));
      return h("div", { class: "item" },
        h("div", { class: "item-head" }, h("span", { class: "num" }, i + 1), head,
          h("div", { class: "row-tools" },
            iconBtn("↑", "Naik", () => move(items, i, -1)), iconBtn("↓", "Turun", () => move(items, i, 1)),
            iconBtn("✕", "Hapus entri", () => remove(items, i, "Hapus entri ini?"), "del"))),
        h("div", { class: "grid" }, els));
    });
    return h("div", { class: "stack" },
      fields.start || fields.end ? h("small", { class: "hint" }, DATE_HINT) : null,
      list,
      h("button", { type: "button", class: "btn sm", onclick: () => { items.push({}); structural(); } }, "+ Tambah entri"));
  }

  function renderPairs(sec) {
    const f = defOf(sec).fields;
    const items = sec.items;
    return h("div", { class: "stack" },
      sec.type === "skills" ? h("small", { class: "hint" },
        "Kelompokkan per kategori (mis. Bahasa Pemrograman: Python, Go). Kategori boleh dikosongkan.") : null,
      items.map((it, i) => h("div", { class: "pair-row" },
        field(it, "label", { label: f.label }),
        field(it, "value", { label: f.value }),
        h("div", { class: "row-tools" },
          iconBtn("↑", "Naik", () => move(items, i, -1)), iconBtn("↓", "Turun", () => move(items, i, 1)),
          iconBtn("✕", "Hapus", () => remove(items, i), "del")))),
      h("button", { type: "button", class: "btn sm", onclick: () => { items.push({ label: "", value: "" }); structural(); } },
        "+ Tambah baris"));
  }

  function renderSection(sec, i) {
    const def = defOf(sec);
    const isOpen = openSections.has(sec.id);
    const count = def.kind === "text" ? ((sec.text || "").trim() ? "terisi" : "kosong") : `${sec.items.length} entri`;
    const toggle = () => { isOpen ? openSections.delete(sec.id) : openSections.add(sec.id); render(); };

    let body = null;
    if (isOpen) {
      const kindBody = def.kind === "text"
        ? field(sec, "text", { label: "Isi", rows: 6,
            hint: "2–4 kalimat: siapa Anda, pengalaman utama, keahlian kunci, tujuan karier. Pisahkan paragraf dengan baris kosong." })
        : def.kind === "pairs" ? renderPairs(sec) : renderEntries(sec);
      body = h("div", { class: "sec-body" },
        field(sec, "title", { label: sec.type === "custom" ? "Judul section *" : "Judul custom (opsional)",
          placeholder: `Default: ${def.title.id} / ${def.title.en}`,
          onInput: (e) => { titleEl.textContent = e.target.value.trim() || def.title[cv.lang]; } }),
        kindBody);
    }
    const titleEl = h("b", {}, titleOf(sec));
    return h("section", { class: "card sec" + (sec.enabled ? "" : " disabled") + (isOpen ? " open" : "") },
      h("div", { class: "sec-head" },
        h("button", { type: "button", class: "caret", onclick: toggle }, isOpen ? "▾" : "▸"),
        h("div", { class: "sec-title", onclick: toggle }, titleEl,
          h("span", { class: "muted small" }, sec.type === "custom" ? " · kustom · " : " · ", count)),
        h("label", { class: "check", title: "Tampilkan di CV" },
          h("input", { type: "checkbox", checked: sec.enabled,
            onchange: (e) => { sec.enabled = e.target.checked; structural(); } }), " Tampil"),
        h("div", { class: "row-tools" },
          iconBtn("↑", "Naikkan urutan", () => move(D.sections, i, -1)),
          iconBtn("↓", "Turunkan urutan", () => move(D.sections, i, 1)),
          sec.type === "custom"
            ? iconBtn("✕", "Hapus section", () => remove(D.sections, i, `Hapus section "${titleOf(sec)}"?`), "del")
            : null)),
      body);
  }

  function addCustomSection() {
    const title = prompt("Judul section baru (mis. Publikasi, Pelatihan, Volunteer):");
    if (title === null) return;
    const id = Math.random().toString(16).slice(2, 10);
    D.sections.push({ id, type: "custom", title: title.trim(), enabled: true, items: [] });
    openSections.add(id);
    structural();
  }

  // --------------------------------------------------------------- main
  function render() {
    const y = formEl.scrollTop;
    formEl.replaceChildren(
      renderSettings(),
      renderPersonal(),
      renderExtra(),
      renderDetails(),
      h("div", { class: "sections-head" }, h("h2", {}, "Section CV"),
        h("small", { class: "muted" }, "Klik judul untuk membuka. Section kosong otomatis tidak dicetak.")),
      ...D.sections.map(renderSection),
      h("button", { type: "button", class: "btn add-sec", onclick: addCustomSection }, "+ Tambah section kustom"),
    );
    formEl.scrollTop = y;
  }

  render();
})();
