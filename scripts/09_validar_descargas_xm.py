from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_checkpoints import sha256_file


def main() -> int:
    raw_root = ROOT / "data/raw/xm"
    files = sorted(raw_root.glob("**/*.json"))
    report = []
    for path in files:
        if path.name.startswith("_checkpoint"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data in (None, [], {}):
            raise SystemExit(f"Respuesta vacia detectada: {path}")
        report.append({"file": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    out = ROOT / "outputs/run_006/validacion_descargas.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"files": report, "count": len(report)}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archivos JSON validados: {len(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

