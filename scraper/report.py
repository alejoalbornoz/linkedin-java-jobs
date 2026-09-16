"""Genera el reporte HTML + JSON de una corrida."""
import json
from datetime import datetime
from html import escape
from pathlib import Path

CSS = """
:root { --bg:#0f1115; --card:#181b22; --line:#2a2f3a; --txt:#e6e8ee; --muted:#9aa3b2;
        --post:#3b82f6; --job:#10b981; --new:#f59e0b; }
* { box-sizing:border-box; }
body { margin:0; padding:24px 16px; background:var(--bg); color:var(--txt);
       font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
.wrap { max-width:960px; margin:0 auto; }
h1 { font-size:22px; margin:0 0 4px; }
.meta { color:var(--muted); font-size:13px; margin-bottom:16px; }
.bar { display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin-bottom:20px; }
.bar input[type=text] { flex:1; min-width:200px; padding:8px 12px; border-radius:8px;
       border:1px solid var(--line); background:var(--card); color:var(--txt); font-size:14px; }
.bar label { color:var(--muted); font-size:13px; display:flex; gap:6px; align-items:center; }
.bar select { padding:6px 8px; border-radius:8px; border:1px solid var(--line); background:var(--card); color:var(--txt); font-size:13px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px;
        padding:14px 16px; margin-bottom:12px; }
.card.hidden { display:none; }
.top { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }
.badge { font-size:11px; font-weight:600; letter-spacing:.04em; padding:2px 8px; border-radius:999px; color:#fff; }
.badge.post { background:var(--post); } .badge.job { background:var(--job); } .badge.new { background:var(--new); color:#000; }
.badge.seeker { background:#4b5563; }
.score { color:var(--muted); font-size:12px; margin-left:auto; }
.title { font-weight:600; font-size:16px; }
.sub { color:var(--muted); font-size:13px; }
.text { white-space:pre-wrap; margin:10px 0; max-height:9em; overflow:hidden; position:relative; }
.text.open { max-height:none; }
.text:not(.open)::after { content:""; position:absolute; left:0; right:0; bottom:0; height:3em;
        background:linear-gradient(transparent,var(--card)); }
.more { background:none; border:none; color:var(--post); cursor:pointer; padding:0; font-size:13px; }
.links { display:flex; gap:12px; flex-wrap:wrap; margin-top:8px; font-size:13px; }
.links a { color:var(--post); text-decoration:none; } .links a:hover { text-decoration:underline; }
.tags { color:var(--muted); font-size:12px; margin-top:6px; }
.empty { color:var(--muted); text-align:center; padding:40px 0; }
"""

JS = """
const q = document.getElementById('q'), onlyNew = document.getElementById('onlyNew'), sortSel = document.getElementById('sort');
function apply() {
  const s = q.value.toLowerCase();
  for (const c of document.querySelectorAll('.card')) {
    const okText = !s || c.innerText.toLowerCase().includes(s);
    const okNew = !onlyNew.checked || c.dataset.new === '1';
    c.classList.toggle('hidden', !(okText && okNew));
  }
}
// Reordena las tarjetas dentro de cada sección. Las que no tienen fecha (ts=0) van al final.
function sortCards() {
  const mode = sortSel.value;
  for (const sec of document.querySelectorAll('section')) {
    const cards = Array.from(sec.querySelectorAll('.card'));
    cards.sort((a, b) => {
      const sa = +a.dataset.score, sb = +b.dataset.score, ta = +a.dataset.ts, tb = +b.dataset.ts;
      return mode === 'recent' ? (tb - ta) || (sb - sa) : (sb - sa) || (tb - ta);
    });
    cards.forEach(c => sec.appendChild(c));
  }
  try { localStorage.setItem('sort', mode); } catch (e) {}
}
try { const saved = localStorage.getItem('sort'); if (saved) sortSel.value = saved; } catch (e) {}
q.addEventListener('input', apply); onlyNew.addEventListener('change', apply);
sortSel.addEventListener('change', sortCards);
sortCards();
document.querySelectorAll('.more').forEach(b => b.addEventListener('click', () => {
  const t = b.previousElementSibling; t.classList.toggle('open');
  b.textContent = t.classList.contains('open') ? 'Ver menos' : 'Ver más';
}));
apply();
"""


def _card(it: dict) -> str:
    e = escape
    is_post = it["source"] == "post"
    badge = '<span class="badge post">PUBLICACIÓN</span>' if is_post else '<span class="badge job">EMPLEO</span>'
    new = '<span class="badge new">NUEVO</span>' if it.get("new") else ""
    if it.get("seeker_signals"):
        new += '<span class="badge seeker" title="Parece alguien buscando trabajo, no una oferta">BUSCA EMPLEO</span>'
    for flag in it.get("flags", []):
        new += f'<span class="badge seeker" title="Aparece más abajo en el texto, no en el título del puesto">{e(flag).upper()}</span>'
    if is_post:
        title = e(it.get("author") or "(autor desconocido)")
        sub = e(it.get("headline", ""))
        body = it.get("text") or it.get("raw") or ""
    else:
        title = e(it.get("title") or "(sin título)")
        sub = " · ".join(e(x) for x in (it.get("company"), it.get("location")) if x)
        body = it.get("footer", "")

    text_html = ""
    if body:
        text_html = f'<div class="text">{e(body)}</div>'
        if len(body) > 400 or body.count("\n") > 6:
            text_html += '<button class="more">Ver más</button>'

    links = [f'<a href="{e(it["url"])}" target="_blank">Ver en LinkedIn ↗</a>']
    if it.get("author_url"):
        links.append(f'<a href="{e(it["author_url"])}" target="_blank">Perfil del autor ↗</a>')

    tags = "Búsqueda: " + ", ".join(e(s) for s in it.get("searches", []))
    if it.get("lang") and it["lang"] != "unknown":
        tags += f" · Idioma: {e(it['lang'])}"
    if it.get("signals"):
        tags += " · Señales: " + ", ".join(e(s) for s in it["signals"])

    # Hora: lo que mostró LinkedIn ("2 h") + la hora absoluta calculada ("16/09 12:12").
    when = e(it.get("posted", ""))
    ts = 0
    if it.get("posted_at"):
        try:
            dt = datetime.fromisoformat(it["posted_at"])
            ts = int(dt.timestamp() * 1000)
            abs_txt = dt.strftime("%d/%m") if it.get("posted_precision") == "day" else dt.strftime("%d/%m %H:%M")
            when = f"{when} · {abs_txt}" if when and when != abs_txt else abs_txt
        except ValueError:
            pass

    return f"""
<div class="card" data-new="{1 if it.get('new') else 0}" data-ts="{ts}" data-score="{it.get('score', 0)}">
  <div class="top">{badge}{new}<span class="sub">{when}</span>
       <span class="score">puntaje {it.get('score', 0)}</span></div>
  <div class="title">{title}</div>
  <div class="sub">{sub}</div>
  {text_html}
  <div class="links">{''.join(links)}</div>
  <div class="tags">{tags}</div>
</div>"""


def write_report(items: list[dict], out_dir: Path, stamp: str, run_info: dict) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stamp}.json"
    html_path = out_dir / f"{stamp}.html"

    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    posts = [i for i in items if i["source"] == "post"]
    jobs = [i for i in items if i["source"] == "job"]
    n_new = sum(1 for i in items if i.get("new"))

    sections = []
    for name, group in (("Publicaciones", posts), ("Empleos", jobs)):
        if not group:
            continue
        sections.append(f"<section><h2>{name} ({len(group)})</h2>" + "".join(_card(i) for i in group) + "</section>")
    body = "".join(sections) or '<div class="empty">No se encontró nada en esta corrida.</div>'

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ofertas Java · {escape(run_info['date'])}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<h1>Ofertas Java en LinkedIn</h1>
<div class="meta">{escape(run_info['date'])} · {len(posts)} publicaciones · {len(jobs)} empleos · {n_new} nuevos</div>
<div class="bar">
  <input id="q" type="text" placeholder="Filtrar (empresa, tecnología, ciudad...)">
  <label>Orden
    <select id="sort">
      <option value="score">más relevantes</option>
      <option value="recent">más recientes</option>
    </select>
  </label>
  <label><input id="onlyNew" type="checkbox" {'checked' if n_new else ''}> Solo nuevos</label>
</div>
{body}
</div><script>{JS}</script></body></html>"""
    html_path.write_text(html, encoding="utf-8")

    latest = out_dir / "latest.html"
    latest.write_text(html, encoding="utf-8")
    return html_path, json_path
