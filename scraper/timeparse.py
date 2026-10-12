"""Convierte lo que LinkedIn muestra como "hace cuánto" a una fecha/hora absoluta.

Entradas típicas:
  - publicaciones: "4 min", "18 h", "1 d", "2 sem", "ahora" (UI en español) o "4m", "18h", "now" (inglés)
  - empleos: pie de tarjeta "Hace 27 minutos Solicitud sencilla", "Hace 2 horas", "2 hours ago",
             y el atributo datetime del <time>: "2026-09-16" (solo fecha)
La referencia es el momento del scraping (`scraped_at` de cada item).
"""
import re
from datetime import datetime, timedelta

# minutos por unidad
_UNITS = {
    "s": 1 / 60, "seg": 1 / 60, "segundo": 1 / 60, "segundos": 1 / 60, "second": 1 / 60, "seconds": 1 / 60,
    "m": 1, "min": 1, "mins": 1, "minuto": 1, "minutos": 1, "minute": 1, "minutes": 1,
    "h": 60, "hr": 60, "hrs": 60, "hora": 60, "horas": 60, "hour": 60, "hours": 60,
    "d": 1440, "día": 1440, "días": 1440, "dia": 1440, "dias": 1440, "day": 1440, "days": 1440,
    "sem": 10080, "semana": 10080, "semanas": 10080, "w": 10080, "wk": 10080, "week": 10080, "weeks": 10080,
    "mes": 43200, "meses": 43200, "mo": 43200, "month": 43200, "months": 43200,
    "a": 525600, "año": 525600, "años": 525600, "y": 525600, "yr": 525600, "year": 525600, "years": 525600,
}
_NOW = ("ahora", "just now", "now", "hace un momento", "hace instantes")
_REL = re.compile(r"(?:hace\s+)?(\d+)\s*([a-záéíóúñ]+)\.?(?:\s+ago)?", re.IGNORECASE)
_ISO = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2})(?::\d{2})?)?")


def parse_posted(text: str, ref: datetime):
    """Devuelve (datetime, precision) con precision 'minute' o 'day', o (None, None)."""
    if not text:
        return None, None
    t = text.strip()
    m = _ISO.match(t)
    if m:
        if m.group(2):
            return datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M"), "minute"
        return datetime.strptime(m.group(1), "%Y-%m-%d"), "day"
    low = t.lower()
    if any(low.startswith(w) for w in _NOW):
        return ref, "minute"
    for num, unit in _REL.findall(low):
        if unit in _UNITS:
            minutes = int(num) * _UNITS[unit]
            precision = "day" if _UNITS[unit] >= 1440 else "minute"
            return ref - timedelta(minutes=minutes), precision
    return None, None


def assign_periods(items: list[dict], periods: list[dict], ref: datetime | None = None) -> None:
    """Clasifica cada item en la primera ventana que le corresponda por antigüedad.

    Se scrapea una sola vez con la ventana más amplia (una semana) y acá se separa en
    "Últimas 24 h" / "Última semana": pedirle las 24 h a LinkedIn por separado devolvería
    exactamente los mismos avisos (ya vienen ordenados del más nuevo al más viejo).
    """
    if not periods:
        return
    ref = ref or datetime.now()
    ultimo = periods[-1]["name"]
    for it in items:
        it["period"] = ultimo
        if not it.get("posted_at"):
            continue
        try:
            edad = (ref - datetime.fromisoformat(it["posted_at"])).total_seconds() / 3600
        except ValueError:
            continue
        for p in periods:
            if edad <= float(p["max_hours"]):
                it["period"] = p["name"]
                break


def annotate(items: list[dict]) -> None:
    """Agrega `posted_at` (ISO) y `posted_precision` a cada item, in place."""
    for it in items:
        try:
            ref = datetime.fromisoformat(it.get("scraped_at", ""))
        except ValueError:
            ref = datetime.now()
        # En empleos el pie ("Hace 2 horas") es más preciso que el <time> (solo fecha).
        candidates = (it.get("footer"), it.get("posted")) if it["source"] == "job" else (it.get("posted"),)
        for text in candidates:
            dt, precision = parse_posted(text or "", ref)
            if dt:
                it["posted_at"] = dt.isoformat(timespec="minutes")
                it["posted_precision"] = precision
                break
        else:
            it["posted_at"] = ""
            it["posted_precision"] = ""
