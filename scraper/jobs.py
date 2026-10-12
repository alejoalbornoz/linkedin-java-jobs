"""Sección EMPLEOS de LinkedIn, vía el endpoint público de búsqueda.

Desde octubre de 2026 la sección Empleos con sesión iniciada usa clases ofuscadas y
las tarjetas no tienen ni id ni link, así que no se puede scrapear del DOM. En cambio
el endpoint público (`/jobs-guest/jobs/api/seeMoreJobPostings/search`) devuelve HTML
estable, no necesita sesión ni navegador, y acepta los filtros que importan:

  keywords   texto de búsqueda
  geoId      ubicación (Argentina = 100446943; ver README para conseguir otros)
  f_WT       2 = solo remoto (se omite para traer presencial/híbrido/remoto)
  f_TPR      rNNNN = publicados en los últimos NNNN segundos
  sortBy     DD = más recientes primero
  start      paginado, de a 10
"""
import html as html_mod
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
PAGE_SIZE = 10
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

CARD_RE = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
FIELD_RES = {
    "title": re.compile(r'class="base-search-card__title"[^>]*>(.*?)</h3>', re.S),
    "company": re.compile(r'class="base-search-card__subtitle".*?(?:<a[^>]*>)?(.*?)(?:</a>)?\s*</h4>', re.S),
    "location": re.compile(r'class="job-search-card__location"[^>]*>(.*?)</span>', re.S),
    "url": re.compile(r'class="base-card__full-link[^"]*"\s+href="([^"?]+)'),
    "posted": re.compile(r'<time[^>]*datetime="([^"]+)"'),
    "posted_text": re.compile(r'<time[^>]*>(.*?)</time>', re.S),
    "benefit": re.compile(r'class="job-posting-benefits__text"[^>]*>(.*?)</span>', re.S),
}


def _clean(raw: str) -> str:
    """Saca tags, entidades HTML y espacios sobrantes."""
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", html_mod.unescape(txt)).strip()


def build_url(keyword: str, target: dict, hours: int, start: int = 0) -> str:
    params = {
        "keywords": keyword,
        "f_TPR": f"r{int(hours) * 3600}",
        "sortBy": "DD",
        "start": start,
    }
    if target.get("geoId"):
        params["geoId"] = str(target["geoId"])
    elif target.get("location"):
        params["location"] = target["location"]
    if target.get("remote_only"):
        params["f_WT"] = "2"
    return ENDPOINT + "?" + urllib.parse.urlencode(params)


class Pacer:
    """Regula el ritmo de los pedidos solo: se frena cuando LinkedIn devuelve 429.

    Las pausas fijas no sirven acá: el endpoint tolera ritmos muy distintos según el
    momento del día y lo que se haya pedido antes. Entonces se arranca rápido, cada 429
    duplica la espera (hasta un techo) y cada tanda de respuestas buenas la baja de a poco.
    """

    def __init__(self, base=1.0, maximo=12.0):
        self.base = self.espera = base
        self.maximo = maximo
        self.ok_seguidos = 0

    def wait(self):
        time.sleep(random.uniform(self.espera * 0.7, self.espera * 1.3))

    def ok(self):
        self.ok_seguidos += 1
        if self.ok_seguidos >= 5 and self.espera > self.base:
            self.espera = max(self.base, self.espera * 0.7)
            self.ok_seguidos = 0

    def throttled(self):
        self.ok_seguidos = 0
        self.espera = min(self.maximo, max(self.base, self.espera) * 2)


PACER = Pacer()


def fetch(url: str, timeout: int = 25, intentos: int = 3) -> str:
    """Pide una URL reintentando si LinkedIn responde 429 (demasiados pedidos).

    Pasa seguido en el primer pedido de empleos, justo después de scrapear las
    publicaciones. Esperar unos segundos alcanza; sin esto se perdía una tanda entera.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    })
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                datos = resp.read().decode("utf-8", "replace")
            PACER.ok()
            return datos
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503):
                raise
            PACER.throttled()          # a partir de acá todo el ritmo baja
            if intento == intentos - 1:
                raise
            time.sleep((intento + 1) * random.uniform(8, 15))
    raise RuntimeError("inalcanzable")


def parse_cards(page_html: str) -> list[dict]:
    """Corta el HTML en tarjetas y saca los campos de cada una."""
    out = []
    # Cada tarjeta empieza en su data-entity-urn; cortamos entre una y la siguiente.
    bounds = [m.start() for m in CARD_RE.finditer(page_html)] + [len(page_html)]
    for i in range(len(bounds) - 1):
        chunk = page_html[bounds[i]:bounds[i + 1]]
        job_id = CARD_RE.search(chunk).group(1)
        item = {"id": job_id}
        for field, rx in FIELD_RES.items():
            m = rx.search(chunk)
            item[field] = _clean(m.group(1)) if m else ""
        if not item["url"]:
            item["url"] = f"https://www.linkedin.com/jobs/view/{job_id}/"
        # `posted` queda como fecha ISO (2026-10-07) y `footer` con el texto visible.
        item["footer"] = " · ".join(x for x in (item.pop("posted_text", ""), item.pop("benefit", "")) if x)
        if item["title"] or item["company"]:
            out.append(item)
    return out


DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"
DESC_RE = re.compile(r'class="(?:show-more-less-html__markup|description__text)[^"]*"[^>]*>(.*?)</div>', re.S)
CRIT_RE = re.compile(r'criteria-subheader[^>]*>\s*(.*?)\s*</h3>\s*<span[^>]*criteria-text[^>]*>\s*(.*?)\s*</span>', re.S)

# El endpoint público no expone la modalidad como campo (y el filtro f_WT se ignora),
# así que se deduce del título y la descripción.
REMOTE_RE = re.compile(r"\b(100\s*%\s*remot\w*|remot[oa]s?|remote|teletrabajo|tele-?working|"
                       r"home\s?office|work\s+from\s+home|trabajo\s+a\s+distancia)\b", re.I)
HYBRID_RE = re.compile(r"\bh[ií]brid\w*\b|\bhybrid\b", re.I)
ONSITE_RE = re.compile(r"\bpresencial\w*\b|\bon-?site\b|\bin-?office\b", re.I)


def modality(text: str) -> str:
    """'remoto' | 'híbrido' | 'presencial' | '' (no se pudo determinar)."""
    if HYBRID_RE.search(text):
        return "híbrido"
    if REMOTE_RE.search(text):
        return "remoto"
    if ONSITE_RE.search(text):
        return "presencial"
    return ""


def fetch_detail(job_id: str) -> dict:
    """Trae descripción y criterios del aviso (lo que no viene en el listado)."""
    page = fetch(DETAIL_URL.format(job_id))
    desc = DESC_RE.search(page)
    criteria = {_clean(k): _clean(v) for k, v in CRIT_RE.findall(page)}
    return {
        "description": _clean(desc.group(1))[:4000] if desc else "",
        "seniority": criteria.get("Nivel de antigüedad", ""),
        "employment": criteria.get("Tipo de empleo", ""),
        "sector": criteria.get("Sectores", ""),
    }


def enrich(items: list[dict], max_details: int = 120) -> None:
    """Completa los avisos con la descripción y deduce la modalidad.

    Primero los de ubicaciones donde solo sirve el remoto: sin la descripción no se
    puede saber si lo son.
    """
    orden = sorted(items, key=lambda i: not i.get("remote_target"))
    hechos = fallidos = 0
    for it in orden:
        base = f"{it.get('title','')} {it.get('location','')}"
        if hechos >= max_details:
            it["modality"] = modality(base)
            continue
        try:
            it.update(fetch_detail(it["id"]))
            hechos += 1
        except Exception:
            fallidos += 1
        it["modality"] = modality(base + " " + it.get("description", ""))
        PACER.wait()
    if hechos or fallidos:
        print(f"   detalles traídos: {hechos}" + (f" · fallaron: {fallidos}" if fallidos else "")
              + f" · ritmo final: {PACER.espera:.1f}s entre pedidos")


def _targets(cfg: dict) -> list[dict]:
    """Soporta `targets` (varias ubicaciones/modalidades) y el formato viejo."""
    targets = cfg.get("targets")
    if targets:
        return targets
    return [{"name": cfg.get("location") or "ubicación del perfil",
             "location": cfg.get("location", ""),
             "remote_only": cfg.get("remote_only", False)}]


def scrape_jobs(cfg: dict, debug=False) -> list[dict]:
    """Recorre keywords × ubicaciones y devuelve los empleos únicos encontrados."""
    found: dict[str, dict] = {}
    now = datetime.now().isoformat(timespec="seconds")
    hours = int(cfg.get("hours", 24))
    max_pages = int(cfg.get("max_pages", 3))
    time.sleep(random.uniform(3, 6))   # respiro después de scrapear las publicaciones

    for target in _targets(cfg):
        label = target.get("name") or target.get("location") or "sin ubicación"
        if target.get("remote_only"):
            label += " (remoto)"
        for keyword in cfg["keywords"]:
            # f_WT=2 lo ignora el endpoint público: metemos "remoto" en la búsqueda
            # para que LinkedIn priorice avisos que lo mencionan.
            busqueda = " ".join(x for x in (keyword, target.get("keywords_extra")) if x)
            total = 0
            # Cada ubicación puede pedir menos páginas (las del exterior rinden menos).
            for page in range(int(target.get("max_pages", max_pages))):
                url = build_url(busqueda, target, hours, start=page * PAGE_SIZE)
                try:
                    items = parse_cards(fetch(url))
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                    print(f"   ✗ {label} «{keyword}» pág {page + 1}: {e}")
                    break
                for it in items:
                    total += 1
                    if it["id"] in found:
                        if label not in found[it["id"]]["searches"]:
                            found[it["id"]]["searches"].append(label)
                        continue
                    it["source"] = "job"
                    it["searches"] = [f"{keyword} · {label}"]
                    it["target"] = label
                    it["remote_target"] = bool(target.get("remote_only"))
                    it["scraped_at"] = now
                    found[it["id"]] = it
                if len(items) < PAGE_SIZE:
                    break
                PACER.wait()
            print(f"   {label} · «{keyword}»: {total} empleos")
            PACER.wait()

    items = list(found.values())
    if cfg.get("fetch_details", True) and items:
        enrich(items, int(cfg.get("max_details", 120)))
    print(f"\n[Empleos] Total únicos: {len(items)}")
    return items
