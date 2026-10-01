# buscar-trabajo

> Buscador diario de ofertas laborales en LinkedIn: publicaciones + sección Empleos, por perfil
> (Java, Soporte técnico…), filtradas, puntuadas y presentadas en un reporte HTML con solo lo nuevo.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Playwright](https://img.shields.io/badge/playwright-1.47+-green)
![Plataforma](https://img.shields.io/badge/plataforma-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

Buscar trabajo en LinkedIn a mano implica repetir todos los días las mismas búsquedas de
publicaciones ("buscamos java", "vacante java", "#hiring java"...) y recorrer la sección de empleos.
Esta herramienta lo hace por vos: abre Chrome con tu sesión, recorre tus búsquedas de las últimas
24 horas, descarta el ruido (JavaScript cuando buscás Java, posts en portugués, puestos Senior,
gente que *busca* trabajo en vez de ofrecerlo) y te deja un reporte ordenado por relevancia con el
link a cada oferta. Viene con dos perfiles listos —**Java** y **Soporte técnico**— y podés agregar
los que quieras.

## Características

- **Dos fuentes**: búsqueda de *publicaciones* (`/search/results/content/`) y sección *Empleos*
  (`/jobs/search/`), ambas limitadas a las últimas 24 h.
- **Varias búsquedas en paralelo**: definís perfiles con nombre (Java, Soporte técnico, lo que sea),
  cada uno con sus URLs, keywords y filtros, y el reporte los separa en secciones.
- **Sesión persistente**: te logueás una sola vez en una ventana de Chrome; las cookies quedan en
  un perfil propio y no vuelve a pedirte nada.
- **Filtros configurables**: el post tiene que hablar realmente del perfil (Java y no JavaScript,
  soporte y no cualquier mención al pasar), excluir idiomas (`pt` por defecto), excluir por puesto
  (Senior/Sr por defecto, respetando "Semi Senior"/"SSR"), regex libre.
- **Puntaje**: señales de contratación suman ("buscamos", "vacante", "remoto"...), señales de
  candidato restan ("open to work", "mi cv"...), así las ofertas reales quedan arriba.
- **Solo lo nuevo**: recuerda lo que ya te mostró y cada corrida reporta únicamente lo que no viste.
- **Reporte HTML** autocontenido: secciones separadas por búsqueda e idioma (español / inglés),
  buscador, orden por relevancia o por fecha, filtro "solo nuevos", badges, link al post/empleo y al
  perfil del autor. También un `.json` por corrida para procesar con otras herramientas.
- **Ritmo humano**: pausas aleatorias, pocas páginas por corrida, navegador visible.
- **Resistente a cambios de LinkedIn**: soporta la UI nueva (2026) y la vieja, y con `--debug`
  guarda screenshot + HTML de cada página para ajustar selectores rápido.

## Cómo funciona

```
config.json ──► Chrome (tu sesión) ──► publicaciones + empleos ──► filtros ──► puntaje
                                                                                 │
              data/seen.json ◄── marca lo visto ◄── reporte .html/.json ◄────────┘
```

1. Abre Chrome (o Edge/Chromium) con un perfil dedicado en `data/browser_profile/`.
2. Visita cada URL de búsqueda de publicaciones, scrollea para cargar más, expande los "…más" y
   extrae autor, cargo, hora, texto y link de cada post.
3. Recorre la sección Empleos por cada keyword (con paginación) y extrae título, empresa,
   ubicación y fecha.
4. Aplica los filtros y calcula el puntaje de cada resultado.
5. Descarta lo ya visto en corridas anteriores, genera el reporte y lo abre en el navegador.

## Requisitos

- Python 3.11+
- Google Chrome o Microsoft Edge instalado (si no, Playwright puede descargar Chromium)
- Una cuenta de LinkedIn

## Instalación

```bash
git clone https://github.com/<tu-usuario>/buscar-trabajo.git
cd buscar-trabajo
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\pip install -r requirements.txt
```

Linux / macOS:

```bash
.venv/bin/pip install -r requirements.txt
```

Si no tenés Chrome ni Edge: `playwright install chromium` (desde el mismo venv).

## Uso

**Primera vez** — iniciar sesión (se abre Chrome, entrás a LinkedIn con tu cuenta y listo):

```bat
.venv\Scripts\python main.py --login
```

**Todos los días**:

```bat
.venv\Scripts\python main.py
```

En Windows también podés hacer doble clic en `run.bat`. Tarda unos minutos y al terminar abre el
reporte en el navegador.

| Opción             | Qué hace                                                        |
|--------------------|-----------------------------------------------------------------|
| `--only posts`     | solo publicaciones                                              |
| `--only jobs`      | solo sección Empleos                                            |
| `--search <nombre>`| correr solo esa búsqueda (ej. `--search soporte`)               |
| `--all`            | incluir también lo ya visto en corridas anteriores              |
| `--no-open`        | no abrir el reporte al terminar                                 |
| `--debug`          | guardar screenshot + HTML de cada página en `data/debug/`       |
| `--headless`       | sin ventana (LinkedIn suele bloquearlo; usalo solo si te anda)  |
| `--config <ruta>`  | usar otro archivo de configuración                              |

Salida típica en consola:

```
→ Navegador: chrome
✓ Sesión de LinkedIn activa.

[Publicaciones] «buscamos java»
   24 publicaciones en la página
...
[Empleos] «java»
   página 1: 25 empleos
   página 2: 25 empleos

============================================================
  Encontrados: 202 · pasaron el filtro: 138 · nuevos: 63
  Descartados: contenido excluido: 36 · idioma pt: 28
  En el reporte: 45 publicaciones, 64 empleos
  Reporte: data\results\2026-09-15_1504.html
============================================================
```

## Configuración

Todo vive en [`config.json`](config.json), organizado en **búsquedas** con nombre. Cada búsqueda
tiene sus propias URLs, keywords y `must_match`; el resto de los filtros y la configuración del
navegador se comparten:

```json
{
  "searches": [
    { "name": "Java",            "enabled": true, "posts": {…}, "jobs": {…}, "filters": {…} },
    { "name": "Soporte técnico", "enabled": true, "posts": {…}, "jobs": {…}, "filters": {…} }
  ],
  "filters": { … compartidos … },
  "browser": { … },
  "output":  { … }
}
```

Para agregar un perfil nuevo, copiá un bloque de `searches`, cambiale el `name`, las URLs, las
keywords y el `must_match`. Para apagar uno sin borrarlo: `"enabled": false`. Para correr uno solo:
`--search <nombre>`. En el reporte cada búsqueda queda en su propia sección y en el selector
"Búsqueda".

### `searches[].posts` — búsqueda de publicaciones

| Clave         | Descripción                                                                  |
|---------------|------------------------------------------------------------------------------|
| `urls`        | URLs de búsqueda de contenido de LinkedIn (armalas en la web con los filtros que quieras y pegalas acá) |
| `max_scrolls` | cuántas veces scrollea cada búsqueda para cargar más resultados (6)          |

### `searches[].jobs` — sección Empleos

| Clave         | Descripción                                                                  |
|---------------|------------------------------------------------------------------------------|
| `keywords`    | keywords a buscar (`["java", "desarrollador java"]`)                         |
| `location`    | país/ciudad (`"Argentina"`, `"Latinoamérica"`…). Vacío = ubicación de tu perfil |
| `remote_only` | `true` para solo remotos                                                     |
| `hours`       | ventana de tiempo en horas (24)                                              |
| `max_pages`   | páginas de 25 resultados por keyword (2)                                     |

### `filters` — qué se descarta y cómo se puntúa

Se definen una vez a nivel raíz y valen para todas las búsquedas; lo que una búsqueda ponga en su
propio `filters` pisa la clave correspondiente (en la práctica, `must_match`).

| Clave                     | Descripción |
|---------------------------|-------------|
| `must_match`              | regex que el texto de las publicaciones debe cumplir; **se define por búsqueda**. En Java: `\bjava\b(?!\s*script)` (la palabra *java* pero no *javascript*). En Soporte técnico: *soporte técnico/informático*, *mesa de ayuda*, *help desk*, *service desk*, *analista de soporte*, *técnico en sistemas*… Se mira solo el texto del post, no el cargo del autor. |
| `exclude`                 | regex para descartar mirando **todo** el item (autor, empresa, ubicación, texto). Ej. `"Brasil"`. |
| `exclude_languages`       | idiomas a descartar entre `es`, `pt`, `en` (por defecto `["pt"]`). Detección por palabras distintivas en [`scraper/lang.py`](scraper/lang.py); si no puede decidir, conserva. Los idiomas que **no** descartás quedan separados en secciones dentro del reporte. |
| `exclude_content`         | regex para descartar por el **puesto** (por defecto Senior / Sr / Sénior, ignorando "Semi Senior", "Semi Sr", "Semisenior"). Se evalúa en el título del empleo o en las primeras `exclude_content_head_lines` (2) líneas del post. Si aparece más abajo (posts con varias vacantes) se conserva con el badge *MENCIONA SENIOR* y un punto menos. |
| `exclude_content_unless`  | si en la misma línea aparece algo de esta lista (Junior, Jr, SSR, Semi Senior, Trainee, "Sr/Ssr"…) no se descarta: son varios niveles. |
| `hiring_signals`          | términos que suman un punto cada uno ("buscamos", "vacante", "remoto"…). Se buscan como palabra completa. |
| `seeker_signals`          | frases típicas de quien *busca* trabajo ("open to work", "mi cv"…); cada una resta `seeker_penalty` puntos (4) y agrega el badge *BUSCA EMPLEO*. |

### `browser` y `output`

| Clave                 | Descripción                                                          |
|-----------------------|----------------------------------------------------------------------|
| `browser.channels`    | orden de navegadores a intentar (`["chrome", "msedge", "chromium"]`) |
| `browser.profile_dir` | dónde guardar el perfil/sesión (`data/browser_profile`)              |
| `browser.headless`    | `true` para no mostrar ventana (no recomendado)                      |
| `output.open_report`  | abrir el reporte al terminar                                         |

## Estructura del proyecto

```
buscar-trabajo/
├── main.py              # CLI: recorre las búsquedas → filtros → reporte
├── config.json          # búsquedas (Java, Soporte técnico…), filtros, navegador
├── run.bat              # atajo para Windows (doble clic)
├── requirements.txt
└── scraper/
    ├── browser.py       # Chrome con perfil persistente, detección de sesión, scroll, dumps
    ├── posts.py         # búsqueda de publicaciones (UI nueva + fallback UI vieja)
    ├── jobs.py          # sección Empleos con paginación
    ├── filters.py       # must_match / exclusiones / idioma / puntaje
    ├── lang.py          # detector de idioma es/pt/en sin dependencias (texto largo y títulos)
    ├── timeparse.py     # "2 h" / "Hace 27 minutos" / "2026-09-16" -> hora absoluta (posted_at)
    ├── storage.py       # data/seen.json: qué ya se mostró
    └── report.py        # reporte HTML + JSON
```

Archivos generados (ignorados por git):

```
data/
├── browser_profile/   # sesión de Chrome — contiene tus cookies, NO lo subas a ningún lado
├── seen.json          # IDs ya vistos
├── results/           # un .html y un .json por corrida, más latest.html
└── debug/             # screenshots/HTML cuando algo falla o con --debug
```

## Ejecutarlo automáticamente

**Windows** — Programador de tareas → Crear tarea básica → Diariamente → Iniciar un programa:

- Programa: `<ruta al proyecto>\.venv\Scripts\python.exe`
- Argumentos: `main.py`
- Iniciar en: `<ruta al proyecto>`

**Linux / macOS** — `crontab -e`:

```
0 9 * * * cd /ruta/al/proyecto && .venv/bin/python main.py --no-open >> data/cron.log 2>&1
```

En ambos casos hace falta una sesión gráfica abierta: el navegador se muestra en pantalla.

## Notas técnicas (por si LinkedIn cambia el HTML)

LinkedIn cambia su front-end seguido. Si de un día para otro deja de encontrar resultados, corré con
`--debug`, mirá los `.png`/`.html` de `data/debug/` y ajustá `EXTRACT_JS` en
[`scraper/posts.py`](scraper/posts.py) o [`scraper/jobs.py`](scraper/jobs.py).

Cómo está armado hoy (UI nueva de LinkedIn, 2026):

- **Publicaciones**: cada post es un `[role="listitem"]`; el texto está en
  `[data-testid="expandable-text-box"]` y el botón "…más" es `[data-testid="expandable-text-button"]`.
  El link al post no aparece en el HTML: el ID de la *activity* se obtiene del atributo `componentkey`
  de la barra de comentarios (`…-replaceableCommentTools…`), que es un protobuf en base64 cuyo varint
  más grande vale `2 × activityId`. En posts de grupos el URN viene en la URL del grupo. Si LinkedIn
  sirve la UI vieja, el extractor cae a `data-urn` / `update-components-*`.
- **Empleos**: tarjetas `[data-job-id]` / `li[data-occludable-job-id]` (con sesión) o `div.base-card`
  (sin sesión). La lista tiene scroll propio y las tarjetas se renderizan al entrar en pantalla.
- **Scroll**: en la UI nueva la página no scrollea por la ventana sino por un contenedor
  (`main#workspace`); se scrollea ese contenedor y además se envía rueda del mouse, que es lo que
  dispara la carga infinita.
- **Sesión**: se considera iniciada cuando existe la cookie `li_at`.
- **Idioma**: en publicaciones se detecta con palabras funcionales (*el/los/con* vs *the/and/with*);
  en empleos solo hay un título de pocas palabras, así que se recurre al vocabulario del puesto
  (*Desarrollador/Analista* vs *Developer/Engineer*), ignorando tecnicismos que se usan igual en
  ambos idiomas (*software*, *full stack*, *Java*). Un título como "ServiceNow" queda como
  *sin determinar*, en su propia sección. Ojo: es el idioma del **título**, no necesariamente el
  del aviso completo.
- **Fechas**: LinkedIn solo muestra tiempos relativos ("2 h", "Hace 27 minutos"); se convierten a
  hora absoluta usando el momento del scraping como referencia y quedan en `posted_at` (JSON) para
  poder ordenar. En empleos el `<time>` trae solo la fecha, así que se prefiere el pie de la tarjeta.

## Aviso

El scraping automatizado va contra los términos de uso de LinkedIn y puede derivar en restricciones
de la cuenta. Este proyecto está pensado para **uso personal, con tu propia cuenta y a ritmo humano**
(pausas aleatorias, pocas páginas por corrida, una o dos corridas por día). No subas `max_scrolls` /
`max_pages` a valores grandes ni lo uses para recolectar datos de terceros de forma masiva.
Usalo bajo tu propia responsabilidad.
