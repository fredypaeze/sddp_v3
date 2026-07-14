from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_catalog import build_call_plan, build_metric_definitions
from minenergia_sddp.data.xm_checkpoints import is_completed, mark_completed, mark_error, versioned_path
from minenergia_sddp.data.xm_client import XMClient, payload_for_call, save_json


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Descarga controlada XM; bloqueada por defecto.")
    p.add_argument("--execute", action="store_true", help="Habilita solicitudes HTTP reales.")
    p.add_argument("--metric", action="append", help="Target o MetricId a ejecutar. Puede repetirse.")
    p.add_argument("--start-date")
    p.add_argument("--end-date")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-resources", type=int)
    p.add_argument("--resource-filter", help="Filtra lotes cuyo codigo/nombre contenga este texto.")
    return p


def filter_calls(calls: list[dict], metrics: list[str] | None, resource_filter: str | None) -> list[dict]:
    selected = calls
    if metrics:
        wanted = set(metrics)
        selected = [call for call in selected if call["target"] in wanted or call["metric_id"] in wanted]
    if resource_filter:
        needle = resource_filter.upper()
        selected = [
            call
            for call in selected
            if not call.get("filter_values") or any(needle in str(value).upper() for value in call.get("filter_values", []))
        ]
    return selected


def print_plan(calls: list[dict], execute: bool) -> None:
    targets = sorted({call["target"] for call in calls})
    entities = sorted({call["entity"] for call in calls})
    print("XM controlled downloader")
    print(f"execute={execute}")
    print(f"estimated_calls={len(calls)}")
    print(f"targets={targets}")
    print(f"entities={entities}")
    if calls:
        print(f"date_range={calls[0].get('start_date')}..{calls[-1].get('end_date')}")
        print("output_roots=" + ", ".join(sorted({call["output_dir"] for call in calls})[:20]))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    end_date = args.end_date or "2026-07-13"
    metrics = build_metric_definitions(end_date=end_date)
    if args.start_date:
        metrics = [
            metric.__class__(**{**metric.__dict__, "start_date": args.start_date if metric.start_date else None})
            for metric in metrics
        ]
    calls = build_call_plan(metrics, max_resources=args.max_resources)
    calls = filter_calls(calls, args.metric, args.resource_filter)
    print_plan(calls, execute=args.execute)
    if args.dry_run or not args.execute:
        if not args.execute:
            print("Bloqueado por defecto: agregue --execute para solicitudes HTTP reales.")
        print("No se hicieron solicitudes HTTP.")
        return 0

    client = XMClient(execute=True)
    for call in calls:
        out_dir = ROOT / call["output_dir"]
        if args.resume and is_completed(out_dir, call["call_id"]):
            continue
        payload = payload_for_call(call)
        try:
            data = client.post_json(call["url"], payload)
            target = versioned_path(out_dir, call["call_id"], ".json")
            save_json(target, data)
            rows = len(data) if isinstance(data, list) else None
            mark_completed(out_dir, call["call_id"], target, rows=rows)
        except Exception as exc:
            mark_error(out_dir, call["call_id"], str(exc), {"payload": payload, "call": call})
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

