"""Scraping de la sección EMPLEOS (jobs/search) con filtro de últimas N horas."""
from datetime import datetime
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PWTimeout

from .browser import Browser, pause

PAGE_SIZE = 25  # LinkedIn muestra 25 empleos por página

RESULTS_READY = (
    '[data-job-id], [data-occludable-job-id], div.base-card, '
    '.jobs-search-no-results-banner, .jobs-search-results-list, .scaffold-layout__list'
)

# La lista de empleos tiene su propio scroll (no es la ventana) y las tarjetas
# fuera de vista no se renderizan hasta que aparecen. Buscamos el ancestro
# scrolleable de la primera tarjeta y lo scrolleamos de a poco.
SCROLL_LIST_JS = r"""
() => {
  const card = document.querySelector('[data-job-id], [data-occludable-job-id], div.base-card');
  if (!card) return false;
  let el = card.parentElement;
  while (el && el !== document.body) {
    const st = getComputedStyle(el);
    if (el.scrollHeight > el.clientHeight + 50 && /(auto|scroll)/.test(st.overflowY)) {
      const before = el.scrollTop;
      el.scrollBy(0, Math.round(el.clientHeight * 0.8));
      return el.scrollTop !== before;   // false = ya llegamos al final
    }
    el = el.parentElement;
  }
  const before = window.scrollY;
  window.scrollBy(0, Math.round(window.innerHeight * 0.8));
  return window.scrollY !== before;
}
"""

EXTRACT_JS = r"""
() => {
  if (!document.getElementById('__scraper_css')) {
    const st = document.createElement('style');
    st.id = '__scraper_css';
    st.textContent = '.visually-hidden{display:none!important}';
    document.head.appendChild(st);
  }
  const q = (root, sels) => {
    for (const s of sels) { const el = root.querySelector(s); if (el) return el; }
    return null;
  };
  const txt = (el) => {
    if (!el) return '';
    let t = el.innerText.replace(/\s+/g, ' ').trim();
    const h = (t.length - 1) / 2;   // por si igual quedó "X X" duplicado
    if (Number.isInteger(h) && h > 2 && t.slice(0, h) === t.slice(h + 1)) t = t.slice(0, h);
    return t;
  };

  const out = [];
  const seen = new Set();
  const cards = document.querySelectorAll('li[data-occludable-job-id], [data-job-id], div.base-card[data-entity-urn]');
  for (const el of cards) {
    let id = el.getAttribute('data-occludable-job-id') || el.getAttribute('data-job-id');
    if (!id) id = (el.getAttribute('data-entity-urn') || '').split(':').pop();
    if (!id || seen.has(id)) continue;

    const titleEl = q(el, [
      'a.job-card-container__link strong', 'a.job-card-list__title--link strong',
      '.job-card-list__title--link', '.job-card-list__title', '.artdeco-entity-lockup__title',
      'h3.base-search-card__title', 'a[href*="/jobs/view/"]'
    ]);
    let title = txt(titleEl);
    if (!title) { const a = el.querySelector('a[aria-label]'); if (a) title = a.getAttribute('aria-label'); }
    const company = txt(q(el, [
      '.artdeco-entity-lockup__subtitle', '.job-card-container__primary-description',
      '.job-card-container__company-name', 'h4.base-search-card__subtitle'
    ]));
    const location = txt(q(el, [
      '.job-card-container__metadata-wrapper', '.job-card-container__metadata-item',
      '.artdeco-entity-lockup__caption', '.job-search-card__location'
    ]));
    const timeEl = el.querySelector('time');
    const posted = timeEl ? (timeEl.getAttribute('datetime') || txt(timeEl)) : '';
    const footer = txt(q(el, [
      '.job-card-container__footer-wrapper', '.job-card-list__footer-wrapper', '.job-card-container__footer-item'
    ]));

    if (!title && !company) continue;   // tarjeta todavía no renderizada
    seen.add(id);
    out.push({ id, title, company, location, posted, footer });
  }
  return out;
}
"""


def build_url(keyword: str, cfg: dict, start: int = 0) -> str:
    params = {
        "keywords": keyword,
        "f_TPR": f"r{int(cfg.get('hours', 24)) * 3600}",  # publicados en las últimas N horas
        "sortBy": "DD",                                    # más recientes primero
        "start": start,
    }
    if cfg.get("location"):
        params["location"] = cfg["location"]
    if cfg.get("remote_only"):
        params["f_WT"] = "2"
    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


def scrape_jobs(browser: Browser, cfg: dict) -> list[dict]:
    page = browser.page
    found: dict[str, dict] = {}
    now = datetime.now().isoformat(timespec="seconds")
    max_pages = int(cfg.get("max_pages", 2))

    for keyword in cfg["keywords"]:
        print(f"\n[Empleos] «{keyword}»")
        for page_n in range(max_pages):
            url = build_url(keyword, cfg, start=page_n * PAGE_SIZE)
            try:
                browser.goto(url)
                try:
                    page.wait_for_selector(RESULTS_READY, timeout=20_000)
                except PWTimeout:
                    print("   ⚠ No cargó la lista de empleos.")
                    browser.dump(f"jobs_{keyword}_{page_n}", force=True)
                    break

                # Scrollear la lista para que se rendericen todas las tarjetas.
                for _ in range(15):
                    moved = page.evaluate(SCROLL_LIST_JS)
                    pause(0.6, 1.2)
                    if not moved:
                        break

                items = page.evaluate(EXTRACT_JS)
                browser.dump(f"jobs_{keyword}_{page_n}")
                print(f"   página {page_n + 1}: {len(items)} empleos")

                for it in items:
                    if it["id"] in found:
                        found[it["id"]]["searches"].append(keyword)
                        continue
                    it["source"] = "job"
                    it["url"] = f"https://www.linkedin.com/jobs/view/{it['id']}/"
                    it["searches"] = [keyword]
                    it["scraped_at"] = now
                    found[it["id"]] = it

                if len(items) < PAGE_SIZE:
                    break  # no hay más páginas
            except Exception as e:
                print(f"   ✗ Error: {e}")
                browser.dump(f"error_jobs_{keyword}_{page_n}", force=True)
                break

            pause(3, 5)

    print(f"\n[Empleos] Total únicos: {len(found)}")
    return list(found.values())
