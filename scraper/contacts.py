"""Saca del texto de los avisos los datos para postularse: mail, link y teléfono.

En las publicaciones el "cómo postularse" está enterrado en el texto ("envía tu CV a
tal@empresa.com", "postulate acá: https://lnkd.in/xxxx"). Esto lo extrae para poder
mostrarlo como botón en el reporte, en vez de tener que abrir y leer cada post.
"""
import re
import unicodedata

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# URLs con esquema, o acortadores escritos sin http:// (pasa seguido en LinkedIn).
URL_RE = re.compile(
    r"(?:https?://|(?<![\w.@/])(?:lnkd\.in|bit\.ly|wa\.me|forms\.gle|tinyurl\.com)/)[^\s<>\"' ]+",
    re.IGNORECASE,
)

# Solo teléfonos con prefijo internacional: lo demás da demasiados falsos positivos
# (códigos de vacante, años, montos de sueldo).
PHONE_RE = re.compile(r"\+\d{1,3}[\s.\-]?\d[\d\s.()\-]{6,}\d")

# Si alguna de estas palabras está justo antes del link, es un link para postularse
# (y no el portfolio del autor, una nota o "conocé más sobre nosotros").
# Se compara sobre el texto sin acentos, así "Postúlate" también cae acá.
APPLY_CTX = re.compile(
    r"postul|aplic|apply|vacante|empleo|puesto|convocatoria|inscri|registr|formulario|"
    r"\bcv\b|\bhv\b|curriculum|sumate|unite|unete|join|career|reclut|oportunidad|trabaj",
    re.IGNORECASE,
)


def _no_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))

# Basura que suele quedar pegada al final de una URL (puntuación y emojis).
TRAILING = re.compile(r"[^\w/#?&=%~+-]+$")

MAX_EMAILS, MAX_LINKS, MAX_PHONES = 3, 4, 2


def _clean_url(raw: str) -> str:
    url = TRAILING.sub("", raw)
    if not url.lower().startswith("http"):
        url = "https://" + url
    return url


def extract(text: str) -> dict:
    """Devuelve {'emails': [...], 'links': [{'url','apply'}], 'phones': [...]}."""
    if not text:
        return {}

    emails, seen_mail = [], set()
    for m in EMAIL_RE.finditer(text):
        mail = m.group().strip(".").lower()
        if mail not in seen_mail:
            seen_mail.add(mail)
            emails.append(mail)

    links, seen_url = [], set()
    for m in URL_RE.finditer(text):
        url = _clean_url(m.group())
        if url in seen_url:
            continue
        seen_url.add(url)
        before = _no_accents(text[max(0, m.start() - 90):m.start()])
        links.append({"url": url, "apply": bool(APPLY_CTX.search(before))})

    phones, seen_tel = [], set()
    for m in PHONE_RE.finditer(text):
        tel = re.sub(r"\s{2,}", " ", m.group().strip(" .-"))
        digits = re.sub(r"\D", "", tel)
        if 8 <= len(digits) <= 15 and digits not in seen_tel:
            seen_tel.add(digits)
            phones.append(tel)

    out = {}
    if emails:
        out["emails"] = emails[:MAX_EMAILS]
    if links:
        # Primero los links de postulación.
        links.sort(key=lambda l: not l["apply"])
        out["links"] = links[:MAX_LINKS]
    if phones:
        out["phones"] = phones[:MAX_PHONES]
    return out


def annotate(items: list[dict]) -> None:
    """Agrega `contacts` a cada item, in place."""
    for it in items:
        source_text = it.get("text") or it.get("raw") or ""
        it["contacts"] = extract(source_text)
