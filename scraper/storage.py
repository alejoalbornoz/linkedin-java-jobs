"""Registro de resultados ya vistos (para mostrar solo lo nuevo en cada corrida)."""
import json
from pathlib import Path


class Rotation:
    """Reparte las búsquedas entre varias corridas para no saturar a LinkedIn.

    Cada corrida usa solo un tramo de las URLs y la siguiente continúa desde donde
    quedó. Como la ventana de scrapeo es de una semana, lo que hoy no se busca
    aparece igual mañana: no se pierde nada y se hacen la mitad de búsquedas.
    """

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def take(self, key: str, items: list, n: int | None) -> list:
        if not n or n >= len(items):
            return items
        start = self.data.get(key, 0) % len(items)
        self.data[key] = (start + n) % len(items)
        # Si el tramo se pasa del final, sigue desde el principio.
        return [items[(start + i) % len(items)] for i in range(n)]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")


class Seen:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = {"post": {}, "job": {}}

    def is_new(self, item: dict) -> bool:
        return item["id"] not in self.data.setdefault(item["source"], {})

    def mark(self, items: list[dict], when: str):
        for it in items:
            self.data.setdefault(it["source"], {}).setdefault(it["id"], when)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
