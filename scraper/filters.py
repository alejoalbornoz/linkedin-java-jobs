"""Filtrado y puntaje de resultados.

Cada item descartado queda marcado con `it["dropped"] = "<motivo>"` (sobre el mismo
dict que se recibe), así main.py puede mostrar un resumen de por qué se descartó qué.
"""
import re

from .lang import detect


def _compile(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def _compile_words(words):
    """Cada palabra/frase se busca como término completo ("aplica" no matchea "aplicaciones")."""
    return [(w, re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)", re.IGNORECASE)) for w in words]


def _blob(item: dict) -> str:
    """Todo el texto relevante del item, para buscar keywords."""
    fields = ("title", "company", "location", "author", "headline", "text", "raw", "footer")
    return " ".join(str(item.get(f, "")) for f in fields)


def _content(item: dict) -> str:
    """Solo el contenido de la oferta: texto del post, o título del empleo.
    (No incluye el cargo del autor ni la empresa, para no filtrar por lo que dice el recruiter.)"""
    if item["source"] == "post":
        return (item.get("text") or "") + " " + (item.get("raw") or "")
    return item.get("title", "")


def _head_lines(content: str, n: int) -> list[str]:
    """Encabezado del contenido: las primeras `n` líneas no vacías."""
    return [l.strip() for l in content.splitlines() if l.strip()][:n]


def filter_and_score(items: list[dict], cfg: dict) -> list[dict]:
    must = _compile(cfg.get("must_match", []))
    exclude = _compile(cfg.get("exclude", []))
    exclude_content = _compile(cfg.get("exclude_content", []))
    exclude_content_unless = _compile(cfg.get("exclude_content_unless", []))
    head_lines = int(cfg.get("exclude_content_head_lines", 2))
    exclude_langs = set(cfg.get("exclude_languages", []))
    signals = _compile_words(cfg.get("hiring_signals", []))
    seeker = _compile_words(cfg.get("seeker_signals", []))
    seeker_penalty = int(cfg.get("seeker_penalty", 4))

    kept = []
    for it in items:
        blob = _blob(it)
        content = _content(it)
        it.pop("dropped", None)

        # 1) Regex de exclusión sobre TODO (autor, empresa, ubicación, texto...).
        if any(r.search(blob) for r in exclude):
            it["dropped"] = "regex exclude"
            continue

        # 2) Idioma (posts: texto; empleos: título). "unknown" no se descarta.
        it["lang"] = detect(content)
        if it["lang"] in exclude_langs:
            it["dropped"] = f"idioma {it['lang']}"
            continue

        # 3) Las publicaciones tienen que mencionar Java en el TEXTO del post (no vale
        #    que lo diga solo el cargo del autor). Los empleos vienen de una búsqueda
        #    "java", así que los dejamos pasar aunque el título no lo diga.
        if it["source"] == "post" and must and not any(r.search(content) for r in must):
            it["dropped"] = "no menciona java"
            continue

        # 4) Exclusión por contenido del puesto (ej. Senior). Se mira el ENCABEZADO
        #    (primeras líneas del post / título del empleo), que es donde va el rol:
        #    si aparece en una de esas líneas se descarta, salvo que ESA MISMA línea
        #    mencione algo de la lista "unless" (ej. "Sr/Ssr", "Senior y Junior").
        #    Si solo aparece más abajo (posts que listan varias vacantes) se conserva,
        #    marcado y con un punto menos.
        flags = []
        if exclude_content:
            bad_line = any(
                any(r.search(line) for r in exclude_content)
                and not any(r.search(line) for r in exclude_content_unless)
                for line in _head_lines(content, head_lines)
            )
            if bad_line:
                it["dropped"] = "contenido excluido"
                continue
            for r in exclude_content:
                m = r.search(content)
                if m:
                    flags.append(f"menciona {m.group().strip()}")
                    break

        hits = [w for w, r in signals if r.search(blob)]
        seeker_hits = [w for w, r in seeker if r.search(content)]
        score = len(hits) - seeker_penalty * len(seeker_hits) - len(flags)
        if it["source"] == "job":
            score += 3 if any(r.search(it.get("title", "")) for r in must) else 1
        else:
            score += 2

        it["score"] = score
        it["signals"] = hits
        it["seeker_signals"] = seeker_hits
        it["flags"] = flags
        kept.append(it)

    # Más puntaje primero; a igual puntaje, más reciente primero.
    kept.sort(key=lambda x: x.get("posted_at") or "", reverse=True)
    kept.sort(key=lambda x: -x["score"])
    return kept
