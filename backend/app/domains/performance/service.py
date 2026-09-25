"""k6 script generation + real subprocess execution for the performance
domain.

Reuses `api_performer`'s own `apply_substitution`/`resolve_environment`
directly (imported below) to resolve `{{base_url}}`/`{{VARIABLE_NAME}}`
placeholders from the saved request's environment - exactly the substitution
rule api_performer's own execute endpoint applies, not reimplemented here.

Deliberately has NO dependency on Celery/`app.worker`, same reasoning as
`app.domains.executions.tasks`: `app.worker.py` imports this module's
functions (indirectly, via `app.domains.performance.tasks`) rather than the
other way around, keeping this module independently testable/callable
without Celery installed at all.
"""
import json
import subprocess
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.domains.api_performer.models import HttpMethod

# Buffer added on top of the test's own `duration_seconds` before the
# subprocess is considered hung - k6 needs some startup/teardown time beyond
# the pure load-generation window itself.
SUBPROCESS_TIMEOUT_BUFFER_SECONDS = 30


class K6RunError(Exception):
    """Raised by `run_k6_script()` for any failure to produce a usable
    summary (binary not found, timed out, non-zero exit with no parsable
    summary file, ...). Always carries a clear, user-facing message - the
    caller (tasks.py) catches this and records it as `PerformanceTestRun.
    error_message` with `status="failed"`, never lets it bubble into Celery
    unhandled."""


def build_k6_script(
    *,
    method: HttpMethod,
    url: str,
    headers: dict[str, str],
    body: str | None,
    vus: int,
    duration_seconds: int,
) -> str:
    """Generates a k6 JS script as a string. Uses `json.dumps()` to safely
    embed the method/URL/headers/body as JS literals - this avoids hand-
    rolling string escaping (and the injection/quoting bugs that come with
    it): whatever `json.dumps` produces is always a valid JS literal for the
    corresponding JSON-compatible value.

    Uses `http.request(method, url, body, params)` - the generic form -
    rather than method-specific helpers like `http.get`/`http.post`, so
    every `HttpMethod` (including e.g. `PATCH`, `HEAD`) is handled
    uniformly."""
    options_json = json.dumps({"vus": vus, "duration": f"{duration_seconds}s"})
    method_json = json.dumps(method.value)
    url_json = json.dumps(url)
    body_json = json.dumps(body) if body is not None else "null"
    headers_json = json.dumps(headers)
    return (
        "import http from 'k6/http';\n"
        f"export const options = {options_json};\n"
        "export default function () {\n"
        f"  http.request({method_json}, {url_json}, {body_json}, {{ headers: {headers_json} }});\n"
        "}\n"
    )


def _extract_metric(metrics: dict, name: str, key: str) -> float | None:
    """Reads `metrics[name][key]` directly. k6's real `--summary-export` JSON
    (verified against a real k6 v0.54.0 run, not just docs/assumption) puts
    each metric's aggregates directly on the metric object - e.g.
    `http_req_duration: {"avg": ..., "p(95)": ..., ...}` and
    `http_reqs: {"count": ..., "rate": ...}` - there is no intermediate
    `values` wrapper key, unlike an earlier (incorrect) assumption this
    function used to make that silently left every derived metric field
    null while `raw_summary` still captured the real data."""
    metric = metrics.get(name)
    if not isinstance(metric, dict):
        return None
    value = metric.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def parse_k6_summary(summary: dict) -> dict:
    """Extracts the fields `PerformanceTestRun` stores out of k6's
    `--summary-export` JSON shape (a `metrics` dict keyed by metric name,
    each holding its aggregates directly - see `_extract_metric`). Any
    metric that isn't present (e.g. `http_req_failed` missing entirely on
    some k6 versions/configs) simply comes back `None` for that field -
    never raises."""
    metrics = summary.get("metrics") if isinstance(summary, dict) else None
    metrics = metrics if isinstance(metrics, dict) else {}

    request_count = _extract_metric(metrics, "http_reqs", "count")
    # `http_req_failed` is a k6 "rate" metric - its computed fraction lives
    # under the "value" key (not "rate"; "rate" is the throughput key on
    # counter metrics like `http_reqs`, a different metric type).
    error_rate = _extract_metric(metrics, "http_req_failed", "value")
    failed_count: int | None = None
    if request_count is not None and error_rate is not None:
        failed_count = round(request_count * error_rate)

    return {
        "request_count": int(request_count) if request_count is not None else None,
        "failed_count": failed_count,
        "error_rate": error_rate,
        "avg_duration_ms": _extract_metric(metrics, "http_req_duration", "avg"),
        "p95_duration_ms": _extract_metric(metrics, "http_req_duration", "p(95)"),
        "min_duration_ms": _extract_metric(metrics, "http_req_duration", "min"),
        "max_duration_ms": _extract_metric(metrics, "http_req_duration", "max"),
        "requests_per_second": _extract_metric(metrics, "http_reqs", "rate"),
        "raw_summary": summary,
    }


def run_k6_script(script: str, *, duration_seconds: int) -> dict:
    """Writes `script` to a temp file, runs `k6 run --summary-export
    <summary> <script>` as a real subprocess, and returns the parsed metrics
    dict (see `parse_k6_summary`). Cleans up both temp files afterwards,
    success or failure.

    Raises `K6RunError` (never an unhandled exception) if:
      - the k6 binary isn't found on PATH / at `settings.k6_binary_path`
        (`FileNotFoundError`) - the common "k6 isn't installed on this
        dev/CI machine" case;
      - the subprocess times out;
      - the subprocess exits non-zero AND produced no parsable summary file
        (a non-zero exit with a valid summary - e.g. k6's own threshold
        failures - is NOT treated as an error here, since the load test
        itself still produced real, usable metrics).
    """
    settings = get_settings()
    tmp_dir = Path(tempfile.mkdtemp(prefix="genqa_k6_"))
    script_path = tmp_dir / "script.js"
    summary_path = tmp_dir / "summary.json"
    script_path.write_text(script, encoding="utf-8")

    timeout = duration_seconds + SUBPROCESS_TIMEOUT_BUFFER_SECONDS
    cmd = [
        settings.k6_binary_path,
        "run",
        "--summary-export",
        str(summary_path),
        str(script_path),
    ]

    try:
        try:
            subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
        except FileNotFoundError as exc:
            raise K6RunError(
                f"k6 binary not found (looked for '{settings.k6_binary_path}' on PATH). "
                "Install k6 or set K6_BINARY_PATH to point at a portable binary."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise K6RunError(f"k6 run timed out after {timeout}s.") from exc

        if not summary_path.exists():
            raise K6RunError("k6 run did not produce a summary export file.")

        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise K6RunError(f"Failed to parse k6 summary export: {exc}") from exc

        return parse_k6_summary(summary)
    finally:
        for path in (script_path, summary_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
