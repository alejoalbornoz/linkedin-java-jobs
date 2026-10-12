"""Filtrado y puntaje de resultados.

Cada item descartado queda marcado con `it["dropped"] = "<motivo>"` (sobre el mismo
dict que se recibe), así main.py puede mostrar un resumen de por qué se descartó qué.
"""
import re

from .lang import detect, detect_short


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
    """Solo el contenido de la oferta: texto del post, o título + descripción del empleo.
    (No incluye el cargo del autor ni la empresa, para no filtrar por lo que dice el recruiter.)"""
    if item["source"] == "post":
        return (item.get("text") or "") + " " + (item.get("raw") or "")
    return " ".join(x for x in (item.get("title", ""), item.get("description", "")) if x)


def _role_lines(item: dict, n: int) -> list[str]:
    """Dónde buscar el rol del puesto (para excluir Senior y similares).

    En empleos es el título y nada más: si se mirara también la descripción, un
    "junior" mencionado al pasar 2000 caracteres más abajo salvaría a un Senior.
    En publicaciones son las primeras `n` líneas, que es donde va el puesto.
    """
    if item["source"] == "job":
        return [item.get("title", "")]
    texto = (item.get("text") or "") + " " + (item.get("raw") or "")
    return [l.strip() for l in texto.splitlines() if l.strip()][:n]


def _location_fit(item: dict, text: str, rules: dict) -> tuple[int, str]:
    """Puntos por ubicación y una etiqueta.

    En Argentina sirve cualquier modalidad; en el resto de los países, solo remoto.
    Para los empleos se usa la ubicación real y la modalidad deducida del aviso;
    para las publicaciones, lo que diga el texto.
    """
    if not rules:
        return 0, ""
    home = any(t in text for t in rules.get("home_terms", []))
    remote = any(t in text for t in rules.get("remote_terms", []))
    foreign = any(t in text for t in rules.get("foreign_terms", []))

    if item["source"] == "job":
        # El scraper ya sabe de qué país vino y si el aviso es remoto.
        home = home or (item.get("target", "").startswith("Argentina"))
        remote = remote or item.get("modality") == "remoto"
        foreign = foreign or (item.get("remote_target") and not home)

    if home:
        return int(rules.get("home_bonus", 5)), "Argentina"
    if remote:
        return int(rules.get("remote_bonus", 3)), "remoto"
    if foreign:
        return -int(rules.get("foreign_onsite_penalty", 8)), "exterior no remoto"
    return 0, ""


def filter_and_score(items: list[dict], cfg: dict) -> list[dict]:
    must = _compile(cfg.get("must_match", []))
    exclude = _compile(cfg.get("exclude", []))
    exclude_content = _compile(cfg.get("exclude_content", []))
    exclude_content_unless = _compile(cfg.get("exclude_content_unless", []))
    head_lines = int(cfg.get("exclude_content_head_lines", 2))
    exclude_langs = set(cfg.get("exclude_languages", []))
    # Dos listas distintas: "intención de contratar" (buscamos, vacante, postulate) pesa
    # el doble que el "contexto" del aviso (remoto, backend, experiencia), que por sí solo
    # aparece también en posts técnicos o de marketing que no ofrecen trabajo.
    # Si solo hay `hiring_signals` (config viejo) se usa esa lista como contexto.
    intent = _compile_words(cfg.get("intent_signals", []))
    context = _compile_words(cfg.get("context_signals") or cfg.get("hiring_signals", []))
    intent_weight = int(cfg.get("intent_weight", 2))
    context_weight = int(cfg.get("context_weight", 1))
    require_intent = bool(cfg.get("require_intent", False)) and bool(intent)
    seeker = _compile_words(cfg.get("seeker_signals", []))
    seeker_penalty = int(cfg.get("seeker_penalty", 4))
    drop_seekers = bool(cfg.get("drop_seekers", False))
    # Afinidad con el CV: cada nivel de tecnologías pesa distinto y se topea para que
    # un aviso que lista 20 tecnologías no se coma el ranking.
    skills = {tier: _compile_words(terms) for tier, terms in cfg.get("cv_skills", {}).items()}
    skill_weights = cfg.get("cv_weights", {})
    max_per_tier = int(cfg.get("cv_max_per_tier", 4))
    level = _compile_words(cfg.get("level_fit", []))
    level_bonus = int(cfg.get("level_fit_bonus", 3))
    loc_rules = cfg.get("location_fit", {})
    drop_foreign = {"job": bool(loc_rules.get("drop_foreign_onsite_jobs", False)),
                    "post": bool(loc_rules.get("drop_foreign_onsite_posts", False))}

    kept = []
    for it in items:
        blob = _blob(it)
        content = _content(it)
        it.pop("dropped", None)

        # 1) Regex de exclusión sobre TODO (autor, empresa, ubicación, texto...).
        if any(r.search(blob) for r in exclude):
            it["dropped"] = "regex exclude"
            continue

        # 2) Idioma. En posts hay texto de sobra; en empleos solo el título, así que se
        #    usa el detector de textos cortos. "unknown" no se descarta nunca.
        it["lang"] = detect(content) if it["source"] == "post" else detect_short(content)
        if it["lang"] in exclude_langs:
            it["dropped"] = f"idioma {it['lang']}"
            continue

        # 3) Las publicaciones tienen que mencionar Java en el TEXTO del post (no vale
        #    que lo diga solo el cargo del autor). Los empleos vienen de una búsqueda
        #    "java", así que los dejamos pasar aunque el título no lo diga.
        if it["source"] == "post" and must and not any(r.search(content) for r in must):
            it["dropped"] = "no coincide con el perfil"
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
                for line in _role_lines(it, head_lines)
            )
            if bad_line:
                it["dropped"] = "contenido excluido"
                continue
            for r in exclude_content:
                m = r.search(content)
                if m:
                    flags.append(f"menciona {m.group().strip()}")
                    break

        intent_hits = [w for w, r in intent if r.search(content)]
        context_hits = [w for w, r in context if r.search(blob)]
        seeker_hits = [w for w, r in seeker if r.search(content)]

        # 5) Una publicación sin ninguna señal de que estén ofreciendo trabajo casi
        #    siempre es otra cosa (una nota, marketing, "empecé un nuevo puesto").
        #    Los empleos vienen de la sección Empleos: ahí no hace falta pedirlo.
        if require_intent and it["source"] == "post" and not intent_hits:
            it["dropped"] = "sin intención de contratar"
            continue

        # 6) Ubicación: Argentina (cualquier modalidad) > remoto > exterior presencial.
        #    En empleos la ubicación y la modalidad son confiables, así que lo que no
        #    sirve se descarta; en publicaciones solo se penaliza (la detección es por texto).
        loc_text = (blob if it["source"] == "post" else
                    f"{it.get('location','')} {it.get('title','')} {it.get('description','')}").lower()
        loc_points, loc_label = _location_fit(it, loc_text, loc_rules)
        if drop_foreign[it["source"]] and loc_label == "exterior no remoto":
            it["dropped"] = "exterior no remoto"
            continue

        # 7) Afinidad con el CV: tecnologías por nivel, topeadas por nivel.
        skill_hits, skill_points = {}, 0
        for tier, terms in skills.items():
            hits = [w for w, r in terms if r.search(content)]
            if hits:
                skill_hits[tier] = hits
                skill_points += int(skill_weights.get(tier, 1)) * min(len(hits), max_per_tier)

        level_hits = [w for w, r in level if r.search(content)
                      or (it["source"] == "job" and r.search(it.get("seniority", "")))]

        # Si el que publica es un candidato, la afinidad con el CV juega en contra:
        # tiene tu mismo stack justamente porque busca lo mismo que vos. Se anula el
        # bonus de tecnologías para que no compita con las ofertas reales.
        if seeker_hits:
            skill_points = 0

        score = (intent_weight * len(intent_hits) + context_weight * len(context_hits)
                 + skill_points + (level_bonus if level_hits else 0) + loc_points
                 - seeker_penalty * len(seeker_hits) - len(flags))
        if seeker_hits and drop_seekers:
            it["dropped"] = "parece alguien buscando trabajo"
            continue
        if it["source"] == "job":
            score += 3 if any(r.search(it.get("title", "")) for r in must) else 1
        else:
            score += 2

        it["score"] = score
        it["skills"] = skill_hits
        it["skill_points"] = skill_points
        it["level_fit"] = level_hits
        it["location_fit"] = loc_label
        it["intent"] = intent_hits
        it["context"] = context_hits
        it["signals"] = intent_hits + context_hits   # compatibilidad con reportes viejos
        it["seeker_signals"] = seeker_hits
        it["flags"] = flags
        kept.append(it)

    # Más puntaje primero; a igual puntaje, más reciente primero.
    kept.sort(key=lambda x: x.get("posted_at") or "", reverse=True)
    kept.sort(key=lambda x: -x["score"])
    return kept
