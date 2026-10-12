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

- **Dos fuentes**: búsqueda de *publicaciones* (`/search/results/content/`) y sección *Empleos*,
  con dos ventanas de tiempo en el mismo reporte: **últimas 24 h** y **última semana**.
- **Varias búsquedas en paralelo**: definís perfiles con nombre (Java, Soporte técnico, lo que sea),
  cada uno con sus URLs, keywords y filtros, y el reporte los separa en secciones.
- **Sesión persistente**: te logueás una sola vez en una ventana de Chrome; las cookies quedan en
  un perfil propio y no vuelve a pedirte nada.
- **Filtros configurables**: el post tiene que hablar realmente del perfil (Java y no JavaScript,
  soporte y no cualquier mención al pasar), excluir idiomas (`pt` por defecto), excluir por puesto
  (Senior/Sr por defecto, respetando "Semi Senior"/"SSR"), regex libre.
- **Cómo postularse, a un clic**: extrae del texto el mail, el link de postulación y el teléfono, y
  los muestra como botones en la tarjeta, en vez de tener que abrir y leer cada aviso.
- **Puntaje a medida de tu CV**: suma por tus tecnologías (Java/Spring Boot pesan más que AWS o
  Python), por el nivel que te sirve (junior/SSR) y por ubicación — Argentina en cualquier
  modalidad primero, después remoto; el exterior presencial se descarta o se hunde. Además las
  señales de *intención de contratar* pesan el doble que las de contexto, y las de candidato
  ("open to work") restan.
- **Solo lo nuevo**: recuerda lo que ya te mostró y cada corrida reporta únicamente lo que no viste.
- **Reporte HTML** autocontenido: secciones separadas por búsqueda e idioma (español / inglés),
  buscador, orden por relevancia o por fecha, filtros "solo nuevos" y "con contacto", badges, link al
  post/empleo y al perfil del autor. También un `.json` por corrida para procesar con otras
  herramientas.
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
  "periods": [
    { "name": "Últimas 24 h",  "max_hours": 24 },
    { "name": "Última semana", "max_hours": 168 }
  ],
  "searches": [
    { "name": "Java",            "enabled": true, "posts": {…}, "jobs": {…}, "filters": {…} },
    { "name": "Soporte técnico", "enabled": true, "posts": {…}, "jobs": {…}, "filters": {…} }
  ],
  "filters": { … compartidos … },
  "browser": { … },
  "output":  { … }
}
```

### `periods` — las dos ventanas de tiempo

Se scrapea una sola vez con la ventana más amplia (una semana) y cada resultado se clasifica en la
primera ventana que le corresponda por antigüedad. En el reporte son el selector **Periodo**, que es
acumulativo: "Últimas 24 h" muestra solo lo de hoy, "Última semana" muestra todo.

Se hace así a propósito: LinkedIn devuelve los resultados del más nuevo al más viejo, así que pedirle
las 24 h por separado traería exactamente los mismos avisos que ya vienen al pedir la semana —
sería el doble de scrapeo para los mismos datos.

Para agregar un perfil nuevo, copiá un bloque de `searches`, cambiale el `name`, las URLs, las
keywords y el `must_match`. Para apagar uno sin borrarlo: `"enabled": false`. Para correr uno solo:
`--search <nombre>`. En el reporte cada búsqueda queda en su propia sección y en el selector
"Búsqueda".

### `searches[].posts` — búsqueda de publicaciones

| Clave         | Descripción                                                                  |
|---------------|------------------------------------------------------------------------------|
| `urls`        | URLs de búsqueda de contenido de LinkedIn (armalas en la web con los filtros que quieras y pegalas acá) |
| `max_scrolls`      | cuántas veces scrollea cada búsqueda para cargar más resultados (4)   |
| `max_urls_per_run` | cuántas de las `urls` usa cada corrida (4). La siguiente sigue desde donde quedó: en 2 corridas se cubren todas, haciendo la mitad de búsquedas por vez. |
| `pause_between`    | segundos de espera entre búsquedas (`[10, 20]`, al azar en ese rango)  |

### `searches[].jobs` — sección Empleos

| Clave         | Descripción                                                                  |
|---------------|------------------------------------------------------------------------------|
| `keywords`       | keywords a buscar (`["java", "desarrollador java"]`)                      |
| `targets`        | ubicaciones donde buscar, cada una con su `geoId` y opcionalmente `remote_only`. Por defecto: **Argentina** (presencial, híbrido o remoto) y **España / México / Estados Unidos** solo remoto. |
| `hours`          | ventana de tiempo en horas (168 = una semana; los periodos la subdividen)  |
| `max_pages`      | páginas de 10 resultados por keyword y ubicación (2)                       |
| `fetch_details`  | `true`: abre cada aviso para traer la descripción completa, el nivel de antigüedad y deducir la modalidad. Sin esto los empleos se puntúan solo por el título. |
| `max_details`    | tope de avisos a los que se les trae el detalle por corrida (80). Se priorizan los de ubicaciones donde solo sirve el remoto: sin la descripción no se puede saber si lo son. |

Cada ubicación acepta además su propio `max_pages` (las del exterior usan 1, Argentina 2).

El ritmo de los pedidos **se autorregula**: arranca en 1 segundo entre pedidos, cada `429 Too Many
Requests` duplica la espera (hasta 12 s) y cada tanda de respuestas buenas la baja de a poco. Las
pausas fijas no alcanzaban: el endpoint tolera ritmos muy distintos según el momento. Si aun así
una página falla tres veces seguidas, se saltea esa tanda y la corrida sigue.

Cada `target` se ve así:

```json
{ "name": "España", "geoId": "105646813", "remote_only": true, "keywords_extra": "remoto" }
```

`geoId` identifica la ubicación en LinkedIn. Los que vienen configurados: Argentina `100446943`,
México `103323778`, Colombia `100876405`, Chile `104621616`, Uruguay `100867946`,
España `105646813`, Estados Unidos `103644278`. Para conseguir otro, buscá empleos en LinkedIn con
esa ubicación y copiá el `geoId=` de la URL.

`remote_only` **no** se puede delegar en LinkedIn (su filtro `f_WT` se ignora en el endpoint
público), así que se resuelve de dos maneras: `keywords_extra` agrega "remoto"/"remote" a la
búsqueda para que priorice esos avisos, y después se descarta todo lo que la descripción no
confirme como remoto.

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
| `intent_signals`          | señales de que **están ofreciendo trabajo** ("buscamos", "vacante", "estamos contratando", "postulate", "envía tu cv"…). Suman `intent_weight` (2) cada una y se buscan como palabra completa. |
| `require_intent`          | `true` (por defecto): una publicación sin ninguna señal de intención se descarta — es una nota, marketing o "empecé un nuevo puesto", no una oferta. Los empleos están exentos: ya vienen de la sección Empleos. |
| `context_signals`         | palabras que *pintan* un aviso pero no implican que contraten ("remoto", "backend", "spring", "requisitos", "beneficios"…). Suman `context_weight` (1), la mitad que las de intención, para que un post técnico no compita con una oferta real. |
| `seeker_signals`          | frases típicas de quien *busca* trabajo ("open to work", "mi cv"…): cada una resta `seeker_penalty` puntos (6), **anulan el bonus de `cv_skills`** y agregan el badge *BUSCA EMPLEO*. El bonus se anula a propósito: un candidato con tu mismo stack coincide con tu CV justamente porque compite por los mismos puestos. Con `drop_seekers: true` se descartan directamente. |
| `cv_skills`               | tus tecnologías en tres niveles: `core` (Java, Spring Boot, microservicios, JPA…), `stack` (PostgreSQL, Kafka, RabbitMQ, Docker, JUnit, Testcontainers, CQRS, saga…) y `extra` (Python, Node, Redis, AWS, Kubernetes…). Suman `cv_weights` (3 / 2 / 1) por coincidencia, hasta `cv_max_per_tier` (4) por nivel, así un aviso que lista 20 tecnologías no se come el ranking. El badge *CV +N* muestra cuánto sumó. |
| `level_fit`               | términos de seniority que te sirven (junior, jr, ssr, semi senior, trainee, sin experiencia, primer empleo…): suman `level_fit_bonus` (3). Complementa a `exclude_content`, que descarta los Senior. |
| `location_fit`            | **Argentina** (presencial, híbrido o remoto) suma `home_bonus` (10); **remoto** en cualquier lado suma `remote_bonus` (4); el **exterior no remoto** resta `foreign_onsite_penalty` (15). En empleos, donde la ubicación y la modalidad son confiables, `drop_foreign_onsite_jobs` los descarta directamente; en publicaciones solo se penalizan (`drop_foreign_onsite_posts: false`), porque ahí la ubicación se deduce del texto. |

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
    ├── jobs.py          # sección Empleos vía el endpoint público (sin navegador) + detalle de cada aviso
    ├── filters.py       # must_match / exclusiones / idioma / puntaje
    ├── lang.py          # detector de idioma es/pt/en sin dependencias (texto largo y títulos)
    ├── timeparse.py     # "2 h" / "Hace 27 minutos" / "2026-09-16" -> hora absoluta (posted_at)
    ├── contacts.py      # saca del texto el mail, el link de postulación y el teléfono
    ├── storage.py       # data/seen.json: qué ya se mostró
    └── report.py        # reporte HTML + JSON
```

Archivos generados (ignorados por git):

```
data/
├── browser_profile/   # sesión de Chrome — contiene tus cookies, NO lo subas a ningún lado
├── seen.json          # IDs ya vistos
├── rotation.json      # en qué búsqueda quedó la rotación de cada perfil
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
- **Empleos**: ya **no se scrapean del navegador**. En octubre de 2026 LinkedIn rehizo la sección:
  las tarjetas pasaron a tener clases ofuscadas (`gfllid`, `gflanj`), sin `data-job-id`, sin link y
  sin id — imposible de parsear de forma estable. En cambio se usa el endpoint público
  `/jobs-guest/jobs/api/seeMoreJobPostings/search`, que devuelve el HTML clásico
  (`div.base-card`, `data-entity-urn`, `<time datetime>`), no necesita sesión ni navegador, y acepta
  `geoId`, `f_TPR` y paginado de a 10. El detalle de cada aviso sale de
  `/jobs-guest/jobs/api/jobPosting/<id>`, que trae la descripción completa y el nivel de antigüedad.
  Dos limitaciones de ese endpoint: el filtro de modalidad `f_WT` se ignora (la modalidad se deduce
  del título y la descripción) y el parámetro `location` por texto tampoco — hay que usar `geoId`.
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

## Si LinkedIn pausa tu búsqueda

Si hacés demasiadas búsquedas seguidas, LinkedIn corta la búsqueda de la cuenta con el cartel
*"Nuestros sistemas han detectado tráfico de búsqueda inusual proveniente de tu cuenta"*. Es
temporal (se destraba en un rato), pero conviene no forzarlo. La app lo detecta y corta la corrida
con un mensaje claro en vez de llenar el reporte de búsquedas vacías.

Qué hace la app cuando pasa:

1. Lo detecta **apenas carga la página** (no espera el timeout) y corta las publicaciones.
2. **Conserva lo que ya había juntado** en esa corrida.
3. **Sigue con los empleos**, que usan el endpoint público y no dependen de tu cuenta.
4. Genera el reporte igual y avisa en el resumen que faltan publicaciones.

Así que si lo ves, **no hace falta cortar la corrida**: dejala terminar y vas a tener el reporte con
los empleos y las publicaciones que alcanzó a traer.

Para que pase lo menos posible, cada corrida usa solo un tramo de las búsquedas
(`posts.max_urls_per_run`, por defecto 4 de 7) y la siguiente continúa desde donde quedó. Como la
ventana de scrapeo es de una semana, lo que hoy no se busca aparece igual mañana: se hacen la mitad
de búsquedas sin perder nada. El estado de la rotación vive en `data/rotation.json`.

Si aun así te pasa seguido:

- **`--only jobs`** no toca la búsqueda de tu cuenta: siempre funciona.
- Correr **un perfil por vez** (`--search java` un día, `--search soporte` otro).
- Bajar `posts.max_urls_per_run` o `posts.max_scrolls` (viene en 4).
- Subir `posts.pause_between` (viene en 10-20 segundos entre búsquedas).

## Aviso

El scraping automatizado va contra los términos de uso de LinkedIn y puede derivar en restricciones
de la cuenta. Este proyecto está pensado para **uso personal, con tu propia cuenta y a ritmo humano**
(pausas aleatorias, pocas páginas por corrida, una o dos corridas por día). No subas `max_scrolls` /
`max_pages` a valores grandes ni lo uses para recolectar datos de terceros de forma masiva.
Usalo bajo tu propia responsabilidad.
