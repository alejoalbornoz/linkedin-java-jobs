"""Manejo del navegador: sesión persistente de LinkedIn y utilidades comunes."""
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# Si la URL contiene alguno de estos fragmentos, NO hay sesión iniciada.
LOGIN_MARKERS = ("/login", "/authwall", "/checkpoint", "/uas/", "/signup")


def pause(a=1.5, b=3.5):
    """Espera un tiempo aleatorio (segundos) para no parecer un bot."""
    time.sleep(random.uniform(a, b))


class Browser:
    """Context manager que abre Chrome/Edge con un perfil propio (data/browser_profile).

    La primera vez hay que iniciar sesión a mano en la ventana; las siguientes
    corridas reutilizan las cookies guardadas en el perfil.
    """

    def __init__(self, cfg, base_dir: Path, headless=False, debug=False):
        self.cfg = cfg
        self.base_dir = base_dir
        self.headless = headless
        self.debug = debug
        self.debug_dir = base_dir / "data" / "debug"
        self._pw = None
        self.context = None
        self.page = None

    # ---- ciclo de vida -------------------------------------------------
    def __enter__(self):
        self._pw = sync_playwright().start()
        profile_dir = self.base_dir / self.cfg["profile_dir"]
        profile_dir.mkdir(parents=True, exist_ok=True)

        errors = []
        for channel in self.cfg.get("channels", ["chrome", "msedge", "chromium"]):
            try:
                kwargs = dict(
                    user_data_dir=str(profile_dir),
                    headless=self.headless,
                    viewport={"width": 1366, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                )
                if channel != "chromium":
                    kwargs["channel"] = channel
                self.context = self._pw.chromium.launch_persistent_context(**kwargs)
                print(f"→ Navegador: {channel}")
                break
            except Exception as e:  # el canal no está instalado o falló, probamos el siguiente
                errors.append(f"  - {channel}: {str(e).strip().splitlines()[0]}")
        if self.context is None:
            self._pw.stop()
            raise RuntimeError(
                "No pude abrir ningún navegador.\n"
                "  ¿Quedó abierta otra ventana del scraper (o un `main.py --login` corriendo)? Cerrala.\n"
                "  Si no tenés Chrome ni Edge: `.venv\\Scripts\\playwright install chromium`.\n"
                "Errores por navegador:\n" + "\n".join(errors)
            )

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(30_000)
        return self

    def __exit__(self, *exc):
        try:
            if self.context:
                self.context.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._kill_leftovers()

    def _kill_leftovers(self, grace_seconds=15):
        """Chrome a veces tarda en cerrar (o queda colgado) y la próxima corrida falla
        con "sesión de navegador existente". Esperamos un poco y, si sigue vivo, lo matamos."""
        if sys.platform != "win32":
            return
        profile_dir = str(self.base_dir / self.cfg["profile_dir"])
        # Solo procesos del navegador (si no, el propio powershell matchea por el path).
        ps_filter = (
            "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') "
            f"-and $_.CommandLine -like '*{profile_dir}*' }}"
        )
        for _ in range(grace_seconds):
            r = subprocess.run(["powershell", "-NoProfile", "-Command", f"@({ps_filter}).Count"],
                               capture_output=True, text=True)
            if r.stdout.strip() == "0":
                return
            time.sleep(1)
        print("   ⚠ Chrome no cerró solo; lo cierro a la fuerza.")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"{ps_filter} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                       capture_output=True)

    # ---- sesión --------------------------------------------------------
    def _is_logged_in(self) -> bool:
        url = self.page.url
        if any(m in url for m in LOGIN_MARKERS):
            return False
        try:
            # LinkedIn setea la cookie `li_at` recién cuando la sesión está autenticada
            # (después del 2FA si lo hay). Es más estable que buscar elementos del HTML.
            cookies = self.context.cookies("https://www.linkedin.com")
        except Exception:
            return False
        return any(c["name"] == "li_at" and c["value"] for c in cookies)

    def ensure_logged_in(self, wait_seconds=300):
        self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        pause(2, 4)
        if self._is_logged_in():
            print("✓ Sesión de LinkedIn activa.")
            return

        if self.headless:
            raise RuntimeError(
                "No hay sesión iniciada. Ejecutá `python main.py --login` (sin --headless), "
                "iniciá sesión en la ventana y volvé a intentar."
            )

        print("\n" + "=" * 60)
        print("  Iniciá sesión en LinkedIn en la ventana del navegador.")
        print(f"  Espero hasta {wait_seconds // 60} minutos...")
        print("=" * 60 + "\n")
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            time.sleep(3)
            if self._is_logged_in():
                print("✓ Sesión iniciada. Quedó guardada para las próximas corridas.")
                pause(1, 2)
                return
        raise RuntimeError("Se agotó el tiempo de espera sin iniciar sesión.")

    # ---- navegación ----------------------------------------------------
    def goto(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded")
        pause(2.5, 4.5)

    # En la UI nueva de LinkedIn la página no scrollea por la ventana sino por un
    # contenedor (main#workspace). Buscamos el elemento scrolleable más alto y lo
    # llevamos al fondo; además mandamos rueda del mouse (eventos reales) que es
    # lo que dispara la carga infinita.
    _SCROLL_JS = """
    () => {
      let best = null;
      for (const e of document.querySelectorAll('main, div, section')) {
        const s = getComputedStyle(e);
        if (/(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 100
            && (!best || e.scrollHeight > best.scrollHeight)) best = e;
      }
      if (best) best.scrollTop = best.scrollHeight;
      window.scrollTo(0, document.documentElement.scrollHeight);
      return best ? best.tagName + '#' + best.id : 'window';
    }
    """

    def scroll_down(self):
        """Un paso de scroll hacia abajo (contenedor principal + rueda del mouse)."""
        self.page.evaluate(self._SCROLL_JS)
        try:
            self.page.mouse.move(400, 500)
            self.page.mouse.wheel(0, 3000)
        except Exception:
            pass

    # ---- diagnóstico ---------------------------------------------------
    def dump(self, name: str, force=False):
        """Guarda screenshot + HTML en data/debug/ (solo con --debug o si force=True)."""
        if not (self.debug or force):
            return
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() else "_" for c in name)[:60]
        base = self.debug_dir / f"{stamp}_{safe}"
        try:
            self.page.screenshot(path=str(base) + ".png", full_page=True)
            (base.with_suffix(".html")).write_text(self.page.content(), encoding="utf-8")
            print(f"   (debug) guardado {base}.png / .html")
        except Exception as e:
            print(f"   (debug) no pude guardar el dump: {e}")
