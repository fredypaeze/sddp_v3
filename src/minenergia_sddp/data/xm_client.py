"""Cliente XM bloqueado por defecto."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from minenergia_sddp.data.xm_validation import validate_non_empty_response, validate_payload_schema


class ExecutionBlocked(RuntimeError):
    pass


def payload_for_call(call: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"MetricId": call["metric_id"]}
    if call.get("periodicity") != "ListsEntities":
        payload.update(
            {
                "StartDate": call["start_date"],
                "EndDate": call["end_date"],
                "Entity": call["entity"],
            }
        )
        if call.get("filter_values"):
            payload["Filter"] = call["filter_values"]
    validate_payload_schema(payload, call)
    return payload


class XMClient:
    def __init__(self, execute: bool = False, retries: int = 3, backoff_seconds: list[int] | None = None, timeout: int = 60):
        self.execute = execute
        self.retries = retries
        self.backoff_seconds = backoff_seconds or [2, 5, 10]
        self.timeout = timeout

    def post_json(self, url: str, payload: dict[str, Any]) -> Any:
        if not self.execute:
            raise ExecutionBlocked("La ejecucion HTTP esta bloqueada. Use --execute de forma explicita.")
        if not url.lower().startswith("https://"):
            raise ValueError("Solo se permite HTTPS")
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    validate_non_empty_response(data)
                    return data
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries - 1:
                    time.sleep(self.backoff_seconds[min(attempt, len(self.backoff_seconds) - 1)])
        raise RuntimeError(f"Fallo consulta XM despues de {self.retries} intentos: {last_error}")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

