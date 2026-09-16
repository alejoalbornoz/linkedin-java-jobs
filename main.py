"""Buscador de ofertas Java en LinkedIn (publicaciones + sección Empleos).

Uso:
  python main.py                 # corre todo y abre el reporte
  python main.py --login         # solo abre el navegador para iniciar sesión
  python main.py --only posts    # solo publicaciones
  python main.py --only jobs     # solo empleos
  python main.py --all           # incluye lo ya visto en corridas anteriores
  python main.py --debug         # guarda screenshots/HTML en data/debug/
"""
import argparse
import json
import sys
import webbrowser
from collections import Counter
from datetime import datetime
from pathlib import Path

from scraper.browser import Browser
from scraper.filters import filter_and_score
from scraper.jobs import scrape_jobs
from scraper.posts import scrape_posts
from scraper.report import write_report
from scraper.storage import Seen
from scraper.timeparse import annotate

BASE = Path(__file__).resolve().parent

# Que los símbolos (✓ → ⚠) no rompan la salida en consolas/pipes de Windows.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def parse_args():
    ap = argparse.ArgumentParser(description="Busca ofertas Java en LinkedIn.")
    ap.add_argument("--only", choices=["posts", "jobs"], help="correr solo una fuente")
    ap.add_argument("--all", action="store_true", help="incluir resultados ya vistos en corridas anteriores")
    ap.add_argument("--headless", action="store_true", help="sin ventana (requiere sesión ya guardada)")
    ap.add_argument("--no-open", action="store_true", help="no abrir el reporte al terminar")
    ap.add_argument("--debug", action="store_true", help="guardar screenshots y HTML de cada página")
    ap.add_argument("--login", action="store_true", help="solo abrir el navegador para iniciar sesión")
    ap.add_argument("--config", default=str(BASE / "config.json"))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    headless = args.headless or cfg["browser"].get("headless", False)

    data_dir = BASE / "data"
    seen = Seen(data_dir / "seen.json")
    started = datetime.now()
    stamp = started.strftime("%Y-%m-%d_%H%M")

    raw: list[dict] = []
    with Browser(cfg["browser"], BASE, headless=headless, debug=args.debug) as browser:
        browser.ensure_logged_in()
        if args.login:
            print("Listo. La sesión quedó guardada; ya podés correr `python main.py`.")
            return 0

        if cfg["posts"].get("enabled", True) and args.only != "jobs":
            raw += scrape_posts(browser, cfg["posts"])
        if cfg["jobs"].get("enabled", True) and args.only != "posts":
            raw += scrape_jobs(browser, cfg["jobs"])

    annotate(raw)  # "2 h" / "Hace 27 minutos" / "2026-09-16" -> posted_at absoluto
    items = filter_and_score(raw, cfg["filters"])
    for it in items:
        it["new"] = seen.is_new(it)
    seen.mark(items, started.isoformat(timespec="seconds"))
    seen.save()

    to_report = items if args.all else [i for i in items if i["new"]]

    html_path, json_path = write_report(
        to_report, data_dir / "results", stamp,
        {"date": started.strftime("%d/%m/%Y %H:%M")},
    )

    # Resumen en consola
    n_posts = sum(1 for i in to_report if i["source"] == "post")
    n_jobs = sum(1 for i in to_report if i["source"] == "job")
    dropped = Counter(i["dropped"] for i in raw if i.get("dropped"))
    print("\n" + "=" * 60)
    print(f"  Encontrados: {len(raw)} · pasaron el filtro: {len(items)} · nuevos: {sum(i['new'] for i in items)}")
    if dropped:
        print("  Descartados: " + " · ".join(f"{k}: {n}" for k, n in dropped.most_common()))
    print(f"  En el reporte: {n_posts} publicaciones, {n_jobs} empleos")
    print(f"  Reporte: {html_path}")
    print(f"  JSON:    {json_path}")
    print("=" * 60)
    for it in to_report[:15]:
        who = it.get("author") if it["source"] == "post" else f"{it.get('title')} — {it.get('company')}"
        print(f"  [{it['score']:>2}] {'POST' if it['source']=='post' else 'JOB '} {who[:70]}")
    if len(to_report) > 15:
        print(f"  ... y {len(to_report) - 15} más en el reporte.")

    if cfg["output"].get("open_report", True) and not args.no_open:
        webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        sys.exit(130)
    except RuntimeError as e:
        print(f"\n✗ {e}")
        sys.exit(1)
