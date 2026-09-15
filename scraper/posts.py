"""Scraping de la búsqueda de PUBLICACIONES (search/results/content).

LinkedIn tiene dos UIs conviviendo:
  - la nueva ("flagship", 2026): cada post es un [role="listitem"] con atributos
    `componentkey`; el texto está en [data-testid="expandable-text-box"] y el ID
    del post viene codificado (protobuf en base64) en el componentkey de la barra
    de comentarios.
  - la vieja: contenedores con data-urn="urn:li:activity:..." y clases
    `update-components-*`.
El extractor prueba la nueva primero y cae a la vieja si no encuentra nada.
"""
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import TimeoutError as PWTimeout

from .browser import Browser, pause

# Cualquiera de estos indica que la página de resultados ya renderizó algo.
RESULTS_READY = (
    '[data-testid="expandable-text-box"], [role="listitem"][componentkey], '
    '[data-urn^="urn:li:activity:"], [data-id^="urn:li:activity:"], .search-results-container'
)

NO_RESULTS_MARKERS = ("no se han encontrado resultados", "no results found", "no hay resultados",
                      "sin resultados", "no se encontraron")

# Expande todos los "…más" / "…see more" de los posts.
EXPAND_JS = r"""
() => {
  let n = 0;
  for (const b of document.querySelectorAll('button')) {
    const t = (b.innerText || '').trim().toLowerCase();
    const isToggle = b.getAttribute('data-testid') === 'expandable-text-button'
                  || b.classList.contains('feed-shared-inline-show-more-text__see-more-less-toggle');
    if (isToggle || /^(…|\.\.\.)?\s*(más|more|see more|ver más)$/.test(t)) {
      try { b.click(); n++; } catch (e) {}
    }
  }
  return n;
}
"""

# Botón "Mostrar más resultados" al final de la lista (si existe).
LOAD_MORE_JS = r"""
() => {
  const b = document.querySelector('button.scaffold-finite-scroll__load-button');
  if (b && b.offsetParent !== null) { b.click(); return true; }
  return false;
}
"""

EXTRACT_JS = r"""
() => {
  // LinkedIn duplica textos en spans .visually-hidden (para lectores de pantalla).
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
  const clean = (t) => (t || '').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  const lines = (el) => el ? el.innerText.split('\n').map(s => s.trim()).filter(Boolean) : [];
  // "15 min •", "2 h • Editado •", "3 d", "1 sem", "ahora •", "just now"
  const TIME_RE = /^(\d+\s*[a-záéíóúñ]+\.?|ahora|now|just now)(\s*•.*)?$/i;

  // ---- UI nueva -----------------------------------------------------------
  // El componentkey de la barra de comentarios empieza con un protobuf en base64.
  // Adentro (a veces envuelto en uno o dos submensajes) hay un varint que vale
  // 2 * ID de la activity del post. Recorremos el protobuf y nos quedamos con el
  // varint más grande (los IDs de LinkedIn son ~7.5e18; el resto son chicos).
  const protoVarints = (bytes, acc) => {
    let i = 0;
    while (i < bytes.length) {
      const tag = bytes[i++];
      const wt = tag & 7;
      if (wt === 0) {                          // varint
        let v = 0n, shift = 0n, c;
        do { c = bytes[i++]; v |= BigInt(c & 0x7f) << shift; shift += 7n; } while (c >= 0x80 && i < bytes.length);
        acc.push(v);
      } else if (wt === 2) {                   // bytes / submensaje
        const len = bytes[i++];
        const sub = bytes.slice(i, i + len);
        i += len;
        try { protoVarints(sub, acc); } catch (e) {}
      } else {
        break;                                 // tipo no esperado: abandonamos
      }
    }
    return acc;
  };
  const decodeActivityId = (key) => {
    try {
      let b64 = key.split('-replaceable')[0].replace(/-/g, '+').replace(/_/g, '/');
      b64 += '='.repeat((4 - b64.length % 4) % 4);
      const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const big = protoVarints(bytes, []).filter(v => v > 1000000000000000000n);
      if (!big.length) return null;
      return (big.reduce((a, b) => a > b ? a : b) / 2n).toString();
    } catch (e) { return null; }
  };
  // Algunos links (posts de grupos) traen el URN en la query string.
  const activityFromLinks = (root) => {
    for (const a of root.querySelectorAll('a[href]')) {
      const m = decodeURIComponent(a.href).match(/urn:li:activity:(\d+)/);
      if (m) return m[1];
    }
    return null;
  };

  const extractNew = () => {
    const out = [];
    for (const li of document.querySelectorAll('[role="listitem"]')) {
      const boxes = li.querySelectorAll('[data-testid="expandable-text-box"]');
      const tools = li.querySelector('[componentkey*="replaceableCommentTools"]');
      if (!boxes.length && !tools) continue;           // no es un post

      let id = null, url = '';
      // Posts de grupo: el URN viene en un link y es el único que abre bien.
      const actId = activityFromLinks(li) || (tools ? decodeActivityId(tools.getAttribute('componentkey')) : null);
      if (actId) {
        id = 'urn:li:activity:' + actId;
        url = 'https://www.linkedin.com/feed/update/' + id + '/';
      } else {
        const tc = li.querySelector('[componentkey*="translatable-commentary"]');
        const m = tc ? tc.getAttribute('componentkey').match(/shareId=(\d+)/) : null;
        if (m) {
          id = 'urn:li:share:' + m[1];
          url = 'https://www.linkedin.com/feed/update/' + id + '/';
        } else {
          const outer = li.getAttribute('componentkey') || '';
          id = 'flagship:' + outer.replace(/^expanded/, '').replace(/FeedType.*$/, '');
        }
      }

      // Encabezado: subimos desde el link del autor hasta un bloque con >= 3 líneas
      // ("Nombre", "• 2º", "Cargo", "15 min • Editado •", "Seguir").
      const authorLink = q(li, ['a[href*="linkedin.com/in/"]', 'a[href*="linkedin.com/company/"]',
                                'a[href*="linkedin.com/school/"]', 'a[href*="linkedin.com/groups/"]']);
      const isGroup = !!(authorLink && authorLink.href.includes('/groups/'));
      let hdr = [], el = authorLink;
      for (let k = 0; k < 6 && el; k++) {
        el = el.parentElement;
        hdr = lines(el);
        if (hdr.length >= 3) break;
      }
      let author = hdr[0] || '';
      let rest = hdr.slice(1);
      if (isGroup && rest.length) {
        // Post en grupo: ["Nombre del grupo", "Autor • 2º", "20 h •", "Unirse"]
        author = rest[0].split('•')[0].trim();
        rest = ['Grupo: ' + hdr[0]].concat(rest.slice(1));
      }
      rest = rest.filter(s => !s.startsWith('•')
                           && !/^(seguir|follow|unirse|join|concertar una cita|book an appointment)$/i.test(s));
      const timeLine = rest.find(s => TIME_RE.test(s)) || '';
      const posted = timeLine.split('•')[0].trim();
      const headline = rest.find(s => s !== timeLine) || '';

      // Texto: puede haber más de un bloque (repost con comentario + post original).
      const parts = [];
      for (const box of boxes) {
        let t = box.innerText;
        const btn = box.querySelector('button');
        if (btn && btn.innerText) t = t.replace(btn.innerText, '');
        t = clean(t);
        if (t && !parts.includes(t)) parts.push(t);
      }

      out.push({
        id, url,
        author, headline, posted,
        author_url: authorLink ? authorLink.href.split('?')[0] : '',
        text: parts.join('\n\n— — —\n\n'),
        raw: parts.length ? '' : clean(li.innerText).slice(0, 3000),
      });
    }
    return out;
  };

  // ---- UI vieja (data-urn) ------------------------------------------------
  const extractOld = () => {
    const sel = '[data-urn^="urn:li:activity:"], [data-id^="urn:li:activity:"], '
              + '[data-urn^="urn:li:ugcPost:"], [data-urn^="urn:li:share:"]';
    const containers = Array.from(document.querySelectorAll(sel))
      .filter(el => !el.parentElement.closest('[data-urn^="urn:li:"], [data-id^="urn:li:"]'));
    const out = [];
    for (const el of containers) {
      const urn = el.getAttribute('data-urn') || el.getAttribute('data-id');
      if (!urn) continue;
      const txt = (n) => n ? clean(n.innerText) : '';
      const authorEl = q(el, ['.update-components-actor__title', '.update-components-actor__name']);
      const headEl   = q(el, ['.update-components-actor__description']);
      const timeEl   = q(el, ['.update-components-actor__sub-description']);
      const linkEl   = q(el, ['a.update-components-actor__meta-link', 'a.update-components-actor__container-link']);
      const textEl   = q(el, ['.update-components-text', '.feed-shared-update-v2__description', '.break-words']);
      out.push({
        id: urn,
        url: 'https://www.linkedin.com/feed/update/' + urn + '/',
        author: txt(authorEl).split('•')[0].trim(),
        headline: txt(headEl),
        posted: txt(timeEl).split('•')[0].trim(),
        author_url: linkEl ? linkEl.href.split('?')[0] : '',
        text: txt(textEl),
        raw: textEl ? '' : clean(el.innerText).slice(0, 3000),
      });
    }
    return out;
  };

  let items = extractNew();
  if (!items.length) items = extractOld();

  // Deduplicar por id conservando el primero.
  const seen = new Set();
  return items.filter(it => { if (seen.has(it.id)) return false; seen.add(it.id); return true; });
}
"""


def _label(url: str) -> str:
    """Devuelve el keyword de búsqueda de la URL para mostrarlo en el reporte."""
    kw = parse_qs(urlparse(url).query).get("keywords", [""])[0]
    return kw.replace(".", " ") or url


def scrape_posts(browser: Browser, cfg: dict) -> list[dict]:
    page = browser.page
    max_scrolls = int(cfg.get("max_scrolls", 6))
    found: dict[str, dict] = {}
    now = datetime.now().isoformat(timespec="seconds")

    for url in cfg["urls"]:
        label = _label(url)
        print(f"\n[Publicaciones] «{label}»")
        try:
            browser.goto(url)
            try:
                page.wait_for_selector(RESULTS_READY, timeout=20_000)
            except PWTimeout:
                body = (page.evaluate("() => document.body.innerText") or "").lower()
                if any(m in body for m in NO_RESULTS_MARKERS):
                    print("   0 publicaciones (LinkedIn no devolvió resultados)")
                else:
                    print("   ⚠ No cargaron resultados (¿sesión caída o cambió el HTML?).")
                    browser.dump(f"posts_{label}", force=True)
                continue

            # Carga infinita: scrolleamos y apretamos "mostrar más" si aparece.
            # Cortamos antes si dos scrolls seguidos no traen posts nuevos.
            count_js = "() => document.querySelectorAll('[role=\"listitem\"], [data-urn^=\"urn:li:\"]').length"
            last, stale = page.evaluate(count_js), 0
            for _ in range(max_scrolls):
                browser.scroll_down()
                pause(1.5, 3.0)
                page.evaluate(LOAD_MORE_JS)
                cur = page.evaluate(count_js)
                stale = stale + 1 if cur == last else 0
                last = cur
                if stale >= 2:
                    break

            expanded = page.evaluate(EXPAND_JS)
            if expanded:
                pause(1.0, 2.0)

            items = page.evaluate(EXTRACT_JS)
            browser.dump(f"posts_{label}")
            print(f"   {len(items)} publicaciones en la página")

            for it in items:
                it["source"] = "post"
                it["scraped_at"] = now
                if not it.get("url"):
                    it["url"] = it.get("author_url") or url
                if it["id"] in found:
                    # Mismo post encontrado con otro keyword: solo anotamos la búsqueda.
                    found[it["id"]]["searches"].append(label)
                else:
                    it["searches"] = [label]
                    found[it["id"]] = it
        except Exception as e:
            print(f"   ✗ Error en esta búsqueda: {e}")
            browser.dump(f"error_posts_{label}", force=True)

        pause(3, 6)  # respiro entre búsquedas

    print(f"\n[Publicaciones] Total únicas: {len(found)}")
    return list(found.values())
