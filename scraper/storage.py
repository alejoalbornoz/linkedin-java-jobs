"""Registro de resultados ya vistos (para mostrar solo lo nuevo en cada corrida)."""
import json
from pathlib import Path


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
