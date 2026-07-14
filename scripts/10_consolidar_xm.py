from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    raw_root = ROOT / "data/raw/xm"
    files = sorted(path for path in raw_root.glob("**/*.json") if not path.name.startswith("_checkpoint"))
    if not files:
        print("No hay descargas XM para consolidar. Ejecute primero scripts/08_descargar_xm_controlado.py con autorizacion explicita.")
        return 0
    raise SystemExit("Consolidacion pendiente: validar esquemas reales de respuesta antes de transformar datos.")


if __name__ == "__main__":
    raise SystemExit(main())

