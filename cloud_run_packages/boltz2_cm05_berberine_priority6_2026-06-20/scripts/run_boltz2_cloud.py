#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import os
import shlex
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "inputs"
RESULTS = ROOT / "cloud_results"
LOG_DIR = RESULTS / "logs"
STATUS_DIR = RESULTS / "status"
TABLE_DIR = RESULTS / "tables"
HTML_DIR = RESULTS / "html"
OUTPUT_TEMPLATE = RESULTS / "outputs_template"
OUTPUT_FALLBACK = RESULTS / "outputs_no_template_fallback"
ENV_LOG = LOG_DIR / "cloud_environment.log"
RUN_LOG = LOG_DIR / "boltz2_runner.log"
STATUS_TSV = STATUS_DIR / "boltz2_cm05_status.tsv"
SUMMARY_TSV = TABLE_DIR / "boltz2_cm05_summary.tsv"
HTML_OUT = HTML_DIR / "CM05_berberine_priority6_boltz2_cloud_result.html"
RETURN_TAR = RESULTS / "boltz2_cm05_cloud_return.tar.gz"
MANIFEST = ROOT / "tables" / "cloud_priority6_candidate_manifest.tsv"

PARAMS = [
    "--model", "boltz2",
    "--accelerator", os.environ.get("BOLTZ_ACCELERATOR", "gpu"),
    "--devices", os.environ.get("BOLTZ_DEVICES", "1"),
    "--recycling_steps", os.environ.get("BOLTZ_RECYCLING_STEPS", "3"),
    "--sampling_steps", os.environ.get("BOLTZ_SAMPLING_STEPS", "200"),
    "--diffusion_samples", os.environ.get("BOLTZ_DIFFUSION_SAMPLES", "1"),
    "--sampling_steps_affinity", os.environ.get("BOLTZ_SAMPLING_STEPS_AFFINITY", "200"),
    "--diffusion_samples_affinity", os.environ.get("BOLTZ_DIFFUSION_SAMPLES_AFFINITY", "5"),
    "--override",
    "--seed", os.environ.get("BOLTZ_SEED", "20260620"),
]
if os.environ.get("BOLTZ_USE_MSA_SERVER", "1") != "0":
    PARAMS.append("--use_msa_server")
if os.environ.get("BOLTZ_USE_POTENTIALS", "1") != "0":
    PARAMS.append("--use_potentials")

FIELDS = [
    "priority_order", "gene_symbol", "mode_requested", "template_status", "fallback_status",
    "final_status", "route_used", "yaml_file", "output_dir", "runtime_seconds",
    "cif_exists", "confidence_exists", "affinity_exists", "confidence_score", "ptm", "iptm",
    "ligand_iptm", "complex_plddt", "complex_iplddt", "affinity_pred_value",
    "affinity_probability_binary", "cif_file", "confidence_file", "affinity_file", "log_file", "error_tail",
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with RUN_LOG.open("a") as f:
        f.write(line + "\n")


def ensure_dirs() -> None:
    for d in [LOG_DIR, STATUS_DIR, TABLE_DIR, HTML_DIR, OUTPUT_TEMPLATE, OUTPUT_FALLBACK]:
        d.mkdir(parents=True, exist_ok=True)


def run_capture(cmd: list[str], logfile: Path, cwd: Path = ROOT, env: dict[str, str] | None = None) -> int:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("w") as f:
        f.write("$ " + " ".join(shlex.quote(x) for x in cmd) + "\n")
        f.flush()
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=f, stderr=subprocess.STDOUT, text=True)
        f.write(f"\n[exit_code] {proc.returncode}\n")
        return proc.returncode


def tail(path: Path, n: int = 20) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(errors="replace").splitlines()
    return " | ".join(lines[-n:])[:4000]


def read_manifest() -> list[dict[str, str]]:
    with MANIFEST.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def selected_candidates(mode: str) -> list[dict[str, str]]:
    rows = read_manifest()
    if mode == "smoke":
        return rows[:1]
    return rows


def locate_prediction(out_dir: Path, yaml_stem: str) -> tuple[Path | None, Path | None, Path | None, dict, dict]:
    pred_root = out_dir / f"boltz_results_{yaml_stem}" / "predictions" / yaml_stem
    cif_files = sorted(pred_root.glob("*_model_0.cif")) if pred_root.exists() else []
    conf_files = sorted(pred_root.glob("confidence_*_model_0.json")) if pred_root.exists() else []
    aff_files = sorted(pred_root.glob("affinity_*.json")) if pred_root.exists() else []
    conf = {}
    aff = {}
    if conf_files:
        try:
            conf = json.loads(conf_files[0].read_text())
        except Exception as exc:
            conf = {"parse_error": str(exc)}
    if aff_files:
        try:
            aff = json.loads(aff_files[0].read_text())
        except Exception as exc:
            aff = {"parse_error": str(exc)}
    return (
        cif_files[0] if cif_files else None,
        conf_files[0] if conf_files else None,
        aff_files[0] if aff_files else None,
        conf,
        aff,
    )


def env_for_run() -> dict[str, str]:
    env = os.environ.copy()
    default_cache = "/caas_toolbox/boltz2_cm05_cache" if Path("/caas_toolbox").is_dir() and os.access("/caas_toolbox", os.W_OK) else str(ROOT / ".boltz_cache")
    cache = env.get("BOLTZ_CACHE_DIR", default_cache)
    tmp = env.get("TMPDIR", "/caas_toolbox/tmp" if Path("/caas_toolbox").is_dir() and os.access("/caas_toolbox", os.W_OK) else str(ROOT / "tmp"))
    Path(cache).mkdir(parents=True, exist_ok=True)
    Path(tmp).mkdir(parents=True, exist_ok=True)
    env["BOLTZ_CACHE_DIR"] = cache
    env["TMPDIR"] = tmp
    return env


def write_environment(env: dict[str, str]) -> None:
    checks = [
        ["pwd"], ["date", "-u"], ["uname", "-a"], ["df", "-h", ".", "/", "/caas_toolbox"],
        ["bash", "-lc", "command -v python && python --version"],
        ["bash", "-lc", "command -v python3 && python3 --version"],
        ["bash", "-lc", "command -v boltz || true; boltz --help | head -40 || true"],
        ["bash", "-lc", "command -v nvidia-smi && nvidia-smi || true"],
        ["bash", "-lc", "python - <<'PY'\ntry:\n import torch\n print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'count', torch.cuda.device_count())\nexcept Exception as e:\n print('torch_error', e)\nPY"],
    ]
    with ENV_LOG.open("w") as f:
        f.write(f"run_started_utc={now()}\nroot={ROOT}\n")
        f.write(f"BOLTZ_CACHE_DIR={env.get('BOLTZ_CACHE_DIR')}\nTMPDIR={env.get('TMPDIR')}\n")
        for cmd in checks:
            f.write("\n$ " + " ".join(shlex.quote(c) for c in cmd) + "\n")
            try:
                proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)
                f.write(proc.stdout)
                f.write(proc.stderr)
                f.write(f"[exit_code] {proc.returncode}\n")
            except Exception as exc:
                f.write(f"[exception] {exc}\n")


def run_one(row: dict[str, str], mode: str, env: dict[str, str]) -> dict[str, str]:
    gene = row["gene_symbol"]
    prio = row["priority_order"]
    template_yaml = ROOT / row["template_yaml"]
    fallback_yaml = ROOT / row["no_template_yaml"]
    template_stem = template_yaml.stem
    fallback_stem = fallback_yaml.stem
    t0 = time.time()
    template_log = LOG_DIR / f"{prio}_{gene}_template.log"
    fallback_log = LOG_DIR / f"{prio}_{gene}_fallback.log"

    force_no_template = os.environ.get("BOLTZ_FORCE_NO_TEMPLATE", "0") == "1"
    if force_no_template:
        log(f"running {gene} no-template route directly")
        template_code = None
        template_has_outputs = False
        template_status = "skipped_force_no_template"
    else:
        log(f"running {gene} template")
        template_cmd = ["boltz", "predict", str(template_yaml), "--out_dir", str(OUTPUT_TEMPLATE), "--cache", env["BOLTZ_CACHE_DIR"], *PARAMS]
        template_code = run_capture(template_cmd, template_log, env=env)
        t_cif, t_conf_file, t_aff_file, _t_conf, _t_aff = locate_prediction(OUTPUT_TEMPLATE, template_stem)
        template_has_outputs = bool(t_cif and t_conf_file and t_aff_file)
        if template_code == 0 and template_has_outputs:
            template_status = "success"
        elif template_code == 0 and not template_has_outputs:
            template_status = "missing_outputs"
        else:
            template_status = f"failed:{template_code}"
    route = "template"
    final_log = template_log
    final_out = OUTPUT_TEMPLATE
    final_stem = template_stem
    fallback_status = "not_run"

    allow_fallback = os.environ.get("BOLTZ_ALLOW_FALLBACK", "1") != "0"
    if allow_fallback and (force_no_template or template_code != 0 or not template_has_outputs):
        log(f"{gene} template route status {template_status}; trying no-template fallback")
        fallback_cmd = ["boltz", "predict", str(fallback_yaml), "--out_dir", str(OUTPUT_FALLBACK), "--cache", env["BOLTZ_CACHE_DIR"], *PARAMS]
        fallback_code = run_capture(fallback_cmd, fallback_log, env=env)
        route = "no_template_fallback"
        final_log = fallback_log
        final_out = OUTPUT_FALLBACK
        final_stem = fallback_stem
        f_cif, f_conf_file, f_aff_file, _f_conf, _f_aff = locate_prediction(final_out, final_stem)
        fallback_has_outputs = bool(f_cif and f_conf_file and f_aff_file)
        if fallback_code == 0 and fallback_has_outputs:
            fallback_status = "success"
        elif fallback_code == 0 and not fallback_has_outputs:
            fallback_status = "missing_outputs"
        else:
            fallback_status = f"failed:{fallback_code}"
    else:
        fallback_code = None

    cif, conf_file, aff_file, conf, aff = locate_prediction(final_out, final_stem)
    final_status = "success" if cif and conf_file and aff_file else "missing_outputs"
    if route == "template" and template_code not in (None, 0):
        final_status = "failed"
    if route == "no_template_fallback" and fallback_code not in (None, 0):
        final_status = "failed"
    return {
        "priority_order": prio,
        "gene_symbol": gene,
        "mode_requested": mode,
        "template_status": template_status,
        "fallback_status": fallback_status,
        "final_status": final_status,
        "route_used": route,
        "yaml_file": str(template_yaml if route == "template" else fallback_yaml),
        "output_dir": str(final_out),
        "runtime_seconds": f"{time.time() - t0:.1f}",
        "cif_exists": str(bool(cif)),
        "confidence_exists": str(bool(conf_file)),
        "affinity_exists": str(bool(aff_file)),
        "confidence_score": conf.get("confidence_score", ""),
        "ptm": conf.get("ptm", ""),
        "iptm": conf.get("iptm", ""),
        "ligand_iptm": conf.get("ligand_iptm", ""),
        "complex_plddt": conf.get("complex_plddt", ""),
        "complex_iplddt": conf.get("complex_iplddt", ""),
        "affinity_pred_value": aff.get("affinity_pred_value", ""),
        "affinity_probability_binary": aff.get("affinity_probability_binary", ""),
        "cif_file": str(cif) if cif else "",
        "confidence_file": str(conf_file) if conf_file else "",
        "affinity_file": str(aff_file) if aff_file else "",
        "log_file": str(final_log),
        "error_tail": tail(final_log),
    }


def write_rows(rows: list[dict[str, str]]) -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    for path in [STATUS_TSV, SUMMARY_TSV]:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)


def fmt(x) -> str:
    if x is None:
        return ""
    s = str(x)
    try:
        if s not in ["", "True", "False"]:
            return f"{float(s):.4g}"
    except Exception:
        pass
    return html.escape(s)


def write_html(rows: list[dict[str, str]]) -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    visible = ["priority_order", "gene_symbol", "final_status", "route_used", "confidence_score", "iptm", "ligand_iptm", "complex_plddt", "complex_iplddt", "affinity_pred_value", "affinity_probability_binary", "runtime_seconds"]
    head = "".join(f"<th>{html.escape(k)}</th>" for k in visible)
    body = "".join("<tr>" + "".join(f"<td>{fmt(r.get(k,''))}</td>" for k in visible) + "</tr>" for r in rows)
    ok = sum(1 for r in rows if r.get("final_status") == "success")
    doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>CM05 berberine Boltz2 result</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:32px;line-height:1.5;color:#172033}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border:1px solid #d8e0ea;padding:8px;vertical-align:top}}th{{background:#edf3f8;text-align:left}}.note{{background:#fff8e8;border-left:4px solid #c48900;padding:12px;margin:18px 0}}.ok{{font-size:22px;font-weight:700}}</style></head><body><h1>CM05 berberine priority candidates: Boltz2 result</h1><p class='ok'>Completed targets: {ok} / {len(rows)}</p><p class='note'>Boltz2 outputs are computational prioritization results for follow-up selection. They are not experimental binding evidence.</p><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></body></html>"""
    HTML_OUT.write_text(doc)


def write_status_md(rows: list[dict[str, str]], mode: str) -> None:
    ok = sum(1 for r in rows if r.get("final_status") == "success")
    md = RESULTS / "cloud_run_status.md"
    md.write_text("\n".join([
        "# CM05 berberine Boltz2 Cloud Status",
        "",
        f"- run_finished_utc: {now()}",
        f"- mode: {mode}",
        f"- package_dir: {ROOT}",
        f"- completed_targets: {ok}/{len(rows)}",
        f"- status_tsv: {STATUS_TSV}",
        f"- html: {HTML_OUT}",
        f"- return_tar: {RETURN_TAR}",
        "",
        "## Scientific Boundary",
        "Boltz2 outputs are computational prioritization results for follow-up selection. They are not experimental binding evidence.",
        "",
    ]))


def make_tar() -> None:
    if RETURN_TAR.exists():
        RETURN_TAR.unlink()
    with tarfile.open(RETURN_TAR, "w:gz") as tar:
        for path in [ENV_LOG, RUN_LOG, STATUS_TSV, SUMMARY_TSV, HTML_OUT, RESULTS / "cloud_run_status.md"]:
            if path.exists():
                tar.add(path, arcname=str(path.relative_to(ROOT)))
        for log_file in sorted(LOG_DIR.glob("*.log")):
            if log_file.exists():
                tar.add(log_file, arcname=str(log_file.relative_to(ROOT)))


def main() -> int:
    ensure_dirs()
    mode = os.environ.get("BOLTZ_RUN_MODE", "smoke")
    if mode not in {"smoke", "formal"}:
        raise SystemExit(f"BOLTZ_RUN_MODE must be smoke or formal, got {mode}")
    env = env_for_run()
    write_environment(env)
    rows: list[dict[str, str]] = []
    try:
        version_code = run_capture(["bash", "-lc", "command -v boltz && boltz --help | head -40"], LOG_DIR / "boltz_help.log", env=env)
        if version_code != 0:
            log("boltz is unavailable before candidate runs")
        for row in selected_candidates(mode):
            try:
                result = run_one(row, mode, env)
            except Exception as exc:
                result = {k: "" for k in FIELDS}
                result.update({
                    "priority_order": row.get("priority_order", ""),
                    "gene_symbol": row.get("gene_symbol", ""),
                    "mode_requested": mode,
                    "final_status": "runner_exception",
                    "error_tail": repr(exc),
                })
            rows.append(result)
            write_rows(rows)
            write_html(rows)
            write_status_md(rows, mode)
    finally:
        write_rows(rows)
        write_html(rows)
        write_status_md(rows, mode)
        make_tar()
    # Exit 0 so Codex Cloud returns diagnostic files even when scientific run fails.
    return 0

if __name__ == "__main__":
    sys.exit(main())
