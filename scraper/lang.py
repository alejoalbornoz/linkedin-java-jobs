"""Detección de idioma liviana (es / pt / en) por palabras funcionales distintivas.

No usa librerías: cuenta cuántas palabras "marcadoras" de cada idioma aparecen en el
texto y se queda con el idioma que más tiene. Para posts de ofertas laborales alcanza
de sobra; si un texto es muy corto o mezcla idiomas devuelve "unknown" (y no se filtra).
Solo se usan palabras que NO existen con esa misma grafía en los otros dos idiomas
(por eso no están "para", "que", "empresa", "remoto", "está"...).
"""
import re

MARKERS = {
    "es": {
        "el", "los", "las", "es", "y", "con", "del", "al", "un", "una", "unos", "unas", "en", "sin",
        "más", "también", "trabajo", "desarrollador", "desarrolladora", "experiencia", "años", "año",
        "búsqueda", "busqueda", "oportunidad", "oportunidades", "nuestro", "nuestra", "nuestros",
        "nuestras", "conocimiento", "conocimientos", "equipo", "beneficios", "sueldo", "salario",
        "postulate", "postúlate", "postularse", "envía", "envia", "enviá", "hoy", "aquí", "aqui",
        "ahora", "tienes", "tenés", "tenes", "sos", "eres", "hay", "muy", "pero", "porque", "cómo",
        "dónde", "donde", "cuándo", "cuál", "este", "esta", "estos", "estas", "ese", "esa", "esos",
        "esas", "ser", "puesto", "vacante", "vacantes", "empleo", "empleos", "contratación",
        "incorporación", "sumate", "súmate", "buscando", "buscamos", "requerimos", "ofrecemos",
        "modalidad", "híbrido", "hibrido", "presencial", "inglés", "ingles", "nivel", "mensaje",
        "interesados", "interesadas", "escribime", "escríbeme", "contactame", "contáctame",
    },
    "pt": {
        "o", "os", "as", "não", "nao", "você", "voce", "vocês", "é", "são", "sao", "com", "em", "um",
        "uma", "uns", "umas", "do", "da", "dos", "das", "na", "nas", "ao", "à", "às", "pelo", "pela",
        "pelos", "pelas", "mais", "também", "tambem", "sem", "trabalho", "desenvolvedor",
        "desenvolvedora", "experiência", "anos", "ano", "vaga", "vagas", "oportunidade",
        "oportunidades", "nosso", "nossa", "nossos", "nossas", "conhecimento", "conhecimentos",
        "equipe", "benefícios", "beneficios", "salário", "candidate-se", "envie", "currículo",
        "curriculo", "aqui", "agora", "hoje", "tem", "há", "muito", "mas", "onde", "quando",
        "estão", "estao", "pra", "isso", "esse", "essa", "esses", "essas", "aquele", "aquela",
        "ele", "ela", "eles", "elas", "seu", "sua", "seus", "suas", "então", "entao", "sim",
        "obrigado", "obrigada", "fala", "galera", "pessoal", "conosco", "contratando", "estamos",
        "buscando", "buscamos", "requisitos", "diferenciais", "atuação", "atuar", "remoto",
        "híbrido", "presencial", "inglês", "ingles", "nível", "sênior", "senior", "pleno", "júnior",
        "junior", "clt", "pj", "interessados", "interessadas", "mensagem", "chame", "manda",
        "confira", "desafio", "novo", "nova", "novos", "novas", "abertas", "aberta", "brasil",
    },
    "en": {
        "the", "and", "with", "for", "you", "your", "we", "are", "is", "our", "this", "that", "these",
        "those", "hiring", "looking", "experience", "developer", "engineer", "team", "remote",
        "apply", "role", "position", "opportunity", "opportunities", "candidates", "candidate",
        "skills", "years", "please", "send", "resume", "immediate", "consultants", "requirements",
        "benefits", "job", "jobs", "join", "us", "at", "on", "in", "of", "to", "from", "will", "can",
        "have", "has", "new", "now", "here", "who", "what", "where", "when", "should", "must",
        "strong", "knowledge", "location", "onsite", "hybrid", "salary", "contract", "fulltime",
        "full-time", "available", "share", "dm", "reach", "out", "if", "or", "not", "be", "an",
        "as", "by", "it", "its", "their", "they", "about", "more", "than",
    },
}

# "as", "senior", "junior", "beneficios", "ingles", "buscando", "buscamos", "remoto", "híbrido",
# "presencial", "aqui", "estamos", "contratando" aparecen en más de un idioma: sacamos los repetidos
# para que solo cuenten las palabras realmente distintivas.
_shared = {w for lang, ws in MARKERS.items() for w in ws
           if sum(w in other for other in MARKERS.values()) > 1}
MARKERS = {lang: ws - _shared for lang, ws in MARKERS.items()}

# --- Textos cortos (títulos de empleos) ----------------------------------------
# Un título como "GenAI Developer" no tiene palabras funcionales, así que se mira el
# vocabulario del puesto. Solo palabras que distinguen: los tecnicismos y préstamos
# que se usan igual en los tres idiomas (software, full stack, senior, Java...) se
# ignoran, porque aparecen tanto en avisos en español como en inglés.
TITLE_MARKERS = {
    "es": {
        "desarrollador", "desarrolladora", "desarrolladores", "programador", "programadora",
        "analista", "ingeniero", "ingeniera", "arquitecto", "arquitecta", "diseñador", "diseñadora",
        "técnico", "tecnico", "líder", "lider", "jefe", "gerente", "responsable", "especialista",
        "consultor", "consultora", "asesor", "pasante", "becario", "practicante", "sistemas",
        "datos", "redes", "seguridad", "calidad", "pruebas", "proyectos", "proyecto", "soporte",
        "empresa", "ventas", "comercial", "atención", "atencion", "cliente", "clientes",
        "administrativo", "contable", "recursos", "humanos", "experiencia", "conocimientos",
        "trabajo", "empleo", "vacante", "remoto", "remota", "híbrido", "hibrido", "presencial",
        "excluyente", "bilingüe", "bilingue", "medio", "tiempo", "completo", "para", "con", "sin",
        "asistente", "auxiliar", "coordinador", "coordinadora", "jefa", "ingeniería", "ingenieria",
        "informática", "informatica", "estudiante", "finanzas", "compras", "operaciones",
        "corporativo", "gestión", "gestion", "administración", "administracion", "selección",
        "seleccion", "capacitación", "capacitacion", "modelador", "agentes",
    },
    "pt": {
        "desenvolvedor", "desenvolvedora", "engenheiro", "engenheira", "analista", "arquiteto",
        "técnico", "tecnico", "líder", "lider", "gerente", "especialista", "consultor", "estágio",
        "estagio", "estagiário", "estagiario", "vaga", "dados", "redes", "segurança", "seguranca",
        "qualidade", "testes", "projetos", "projeto", "suporte", "empresa", "vendas", "comercial",
        "atendimento", "cliente", "clientes", "experiência", "experiencia", "conhecimentos",
        "trabalho", "emprego", "remoto", "remota", "híbrido", "hibrido", "presencial", "pleno",
        "para", "com", "sem",
    },
    "en": {
        "developer", "engineer", "manager", "specialist", "analyst", "architect", "designer",
        "consultant", "intern", "internship", "associate", "assistant", "director", "officer",
        "administrator", "technician", "remote", "hybrid", "onsite", "work", "data", "networks",
        "security", "quality", "testing", "project", "projects", "support", "sales", "customer",
        "success", "marketing", "human", "resources", "experience", "knowledge", "job", "position",
        "opening", "part", "time", "entry", "level", "with", "for", "and", "the", "of",
        "developers", "engineers", "analysts", "managers", "specialists", "technical", "leader",
        "advisor", "accounting", "finance", "management", "operations", "corporate", "staff",
        "agents", "helpdesk",
    },
}
_title_shared = {w for ws in TITLE_MARKERS.values() for w in ws
                 if sum(w in other for other in TITLE_MARKERS.values()) > 1}
TITLE_MARKERS = {lang: ws - _title_shared for lang, ws in TITLE_MARKERS.items()}

_WORD = re.compile(r"[a-záéíóúñãõâêôçü'-]+", re.IGNORECASE)


def _score(words, markers, min_hits, margin=1.3):
    counts = {lang: sum(1 for w in words if w in ws) for lang, ws in markers.items()}
    best = max(counts, key=counts.get)
    ranked = sorted(counts.values(), reverse=True)
    # Necesita un mínimo de evidencia y sacarle ventaja clara al segundo.
    if ranked[0] < min_hits or ranked[0] < ranked[1] * margin:
        return None
    return best


def detect(text: str, min_hits: int = 2) -> str:
    """Devuelve 'es', 'pt', 'en' o 'unknown'."""
    if not text:
        return "unknown"
    words = [w.lower() for w in _WORD.findall(text)]
    return _score(words, MARKERS, min_hits) or "unknown"


def detect_short(text: str) -> str:
    """Igual que detect() pero para textos cortos (títulos de empleo): si las palabras
    funcionales no alcanzan, decide por el vocabulario del puesto."""
    if not text:
        return "unknown"
    words = [w.lower() for w in _WORD.findall(text)]
    return _score(words, MARKERS, 2) or _score(words, TITLE_MARKERS, 1, margin=2) or "unknown"
