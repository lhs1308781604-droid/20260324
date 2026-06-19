#!/usr/bin/env python3
"""Score Tahoe-100M pseudobulk perturbations with the CHK1i-sensitive ruler.

The script avoids downloading the full Tahoe pseudobulk table. It scans parquet
row-group metadata through HuggingFace's filesystem, locates row groups whose
`drug` value is one of the candidate compounds, then reads only those row groups
and aggregates scores at the drug-cell line-plate-concentration level.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import math
import os
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import HfApi, HfFileSystem, hf_hub_download


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/Users/liuhuashuo/Documents/New project")).resolve()
RESULT_ROOT = Path(
    os.environ.get(
        "RESULT_ROOT",
        str(PROJECT_ROOT / "results/pancancer_chk1i_sensitizer_2026-06-17"),
    )
).resolve()
TAHOE_ROOT = RESULT_ROOT / "tahoe_state_induction"
TABLE_DIR = TAHOE_ROOT / "tables"
LOG_DIR = TAHOE_ROOT / "logs"
QC_DIR = TAHOE_ROOT / "qc"

DATASET_ID = "tahoebio/Tahoe-100M"
HF_PREFIX = f"datasets/{DATASET_ID}/"
PSEUDOBULK_PATH = "metadata/pseudobulk_differential_expression"
SOURCE_VERSION = "HuggingFace snapshot accessed by huggingface_hub at runtime"


@dataclass
class Paths:
    coverage: Path = RESULT_ROOT / "tables/step5_tahoe_candidate_drug_coverage.tsv"
    ruler: Path = RESULT_ROOT / "tables/step3_chk1i_sensitive_resistant_consensus_ruler.tsv"
    up_genes: Path = RESULT_ROOT / "query_packages/chk1i_sensitive_state_up_genes.txt"
    down_genes: Path = RESULT_ROOT / "query_packages/chk1i_sensitive_state_down_genes.txt"
    drug_meta: Path = RESULT_ROOT / "raw_probe/tahoe_hf/metadata/drug_metadata.parquet"
    cell_meta: Path = RESULT_ROOT / "raw_probe/tahoe_hf/metadata/cell_line_metadata.parquet"
    sample_meta: Path = RESULT_ROOT / "raw_probe/tahoe_hf/metadata/sample_metadata.parquet"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str, log_handle: Any | None = None) -> None:
    line = f"[{now()}] {message}"
    print(line, flush=True)
    if log_handle is not None:
        log_handle.write(line + "\n")
        log_handle.flush()


def normalize_text(x: Any) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return str(x).strip()


def split_semicolon(x: Any) -> list[str]:
    text = normalize_text(x)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def load_candidate_manifest(paths: Paths) -> tuple[pd.DataFrame, dict[str, str], set[str]]:
    coverage = pd.read_csv(paths.coverage, sep="\t")
    variant_to_parent: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for _, row in coverage.iterrows():
        parent = normalize_text(row.get("term"))
        sample_drugs = split_semicolon(row.get("sample_drugs"))
        metadata_drugs = split_semicolon(row.get("metadata_drugs"))
        variants = sorted(set(sample_drugs + metadata_drugs))
        for variant in variants:
            variant_to_parent[variant] = parent
            rows.append(
                {
                    "parent_drug": parent,
                    "tahoe_drug_variant": variant,
                    "n_sample_rows_from_coverage": row.get("n_sample_rows", np.nan),
                    "n_drug_metadata_rows_from_coverage": row.get("n_drug_metadata_rows", np.nan),
                }
            )
    manifest = pd.DataFrame(rows)
    if manifest.empty:
        raise RuntimeError("No Tahoe-covered candidate drug variants were found in the coverage table.")
    target_variants = set(manifest["tahoe_drug_variant"].dropna().astype(str))
    return manifest, variant_to_parent, target_variants


def load_metadata(paths: Paths, manifest: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    drug_meta = pd.read_parquet(paths.drug_meta)
    sample_meta = pd.read_parquet(paths.sample_meta)
    cell_meta_raw = pd.read_parquet(paths.cell_meta)

    keep_cols = ["Cell_ID_DepMap", "Cell_ID_Cellosaur", "cell_name", "Organ"]
    cell_meta = (
        cell_meta_raw[keep_cols]
        .dropna(subset=["Cell_ID_DepMap"])
        .drop_duplicates(subset=["Cell_ID_DepMap", "Cell_ID_Cellosaur", "cell_name", "Organ"])
    )
    cell_meta = cell_meta.drop_duplicates(subset=["Cell_ID_DepMap"], keep="first")

    drug_meta = drug_meta.rename(
        columns={
            "moa-broad": "moa_broad",
            "moa-fine": "moa_fine",
            "human-approved": "human_approved",
            "clinical-trials": "clinical_trials",
        }
    )

    sample_subset = sample_meta[sample_meta["drug"].isin(set(manifest["tahoe_drug_variant"]))].copy()
    return drug_meta, cell_meta, sample_subset


def load_ruler(paths: Paths) -> tuple[pd.DataFrame, set[str], set[str], dict[str, float]]:
    ruler = pd.read_csv(paths.ruler, sep="\t")
    required = {"gene", "consensus_z", "abs_consensus_z", "direction_in_chk1i_sensitive_state"}
    missing = required - set(ruler.columns)
    if missing:
        raise RuntimeError(f"Ruler is missing required columns: {sorted(missing)}")
    ruler = ruler.dropna(subset=["gene", "consensus_z"]).copy()
    ruler["gene"] = ruler["gene"].astype(str)
    # Collapse duplicate gene symbols if present, preserving the strongest absolute weight.
    ruler = (
        ruler.sort_values("abs_consensus_z", ascending=False)
        .drop_duplicates(subset=["gene"], keep="first")
        .reset_index(drop=True)
    )
    up_genes = {x.strip() for x in paths.up_genes.read_text().splitlines() if x.strip()}
    down_genes = {x.strip() for x in paths.down_genes.read_text().splitlines() if x.strip()}
    weights = dict(zip(ruler["gene"], ruler["consensus_z"].astype(float)))
    return ruler, up_genes, down_genes, weights


def list_pseudobulk_files(max_files: int | None = None) -> list[str]:
    api = HfApi()
    items = list(
        api.list_repo_tree(
            DATASET_ID,
            repo_type="dataset",
            path_in_repo=PSEUDOBULK_PATH,
            recursive=True,
        )
    )
    paths = sorted(
        item.path
        for item in items
        if getattr(item, "path", "").endswith(".parquet")
    )
    if max_files is not None:
        paths = paths[:max_files]
    if not paths:
        raise RuntimeError("No Tahoe pseudobulk parquet shards were found.")
    return paths


def scan_one_file(repo_path: str, target_variants: set[str], max_retries: int = 2) -> dict[str, Any]:
    out: dict[str, Any] = {
        "file": repo_path,
        "n_row_groups": 0,
        "n_rows": 0,
        "first_drug": None,
        "last_drug": None,
        "matched_row_groups": [],
        "ambiguous_row_groups": [],
        "status": "pending",
        "error": "",
    }
    for attempt in range(max_retries + 1):
        try:
            fs = HfFileSystem()
            with fs.open(HF_PREFIX + repo_path, "rb") as handle:
                pf = pq.ParquetFile(handle)
                names = pf.schema_arrow.names
                drug_idx = names.index("drug")
                out["n_row_groups"] = pf.metadata.num_row_groups
                out["n_rows"] = pf.metadata.num_rows
                for rg in range(pf.metadata.num_row_groups):
                    stats = pf.metadata.row_group(rg).column(drug_idx).statistics
                    if stats is None:
                        continue
                    dmin = stats.min
                    dmax = stats.max
                    if rg == 0:
                        out["first_drug"] = dmin
                    if rg == pf.metadata.num_row_groups - 1:
                        out["last_drug"] = dmax
                    if dmin == dmax and dmin in target_variants:
                        out["matched_row_groups"].append({"row_group": rg, "drug_stat_min": dmin, "drug_stat_max": dmax})
                    elif dmin != dmax:
                        for target in target_variants:
                            if dmin <= target <= dmax:
                                out["ambiguous_row_groups"].append({"row_group": rg, "drug_stat_min": dmin, "drug_stat_max": dmax})
                                break
                out["status"] = "ok"
                return out
        except Exception as exc:  # noqa: BLE001
            out["status"] = "error"
            out["error"] = f"{type(exc).__name__}: {exc}"
            if attempt < max_retries:
                time.sleep(2 + attempt)
            else:
                return out
    return out


def scan_row_groups(
    repo_paths: list[str],
    target_variants: set[str],
    workers: int,
    log_handle: Any | None,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    started = time.time()
    done = 0
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_path = {
            pool.submit(scan_one_file, path, target_variants): path for path in repo_paths
        }
        for fut in futures.as_completed(future_to_path):
            rec = fut.result()
            done += 1
            records.append(rec)
            if done == 1 or done % 25 == 0 or done == len(repo_paths):
                matched = sum(len(x["matched_row_groups"]) for x in records)
                ambiguous = sum(len(x["ambiguous_row_groups"]) for x in records)
                errors = sum(1 for x in records if x["status"] != "ok")
                log(
                    f"footer scan progress {done}/{len(repo_paths)} files; exact_row_groups={matched}; ambiguous_range_row_groups={ambiguous}; errors={errors}; elapsed={time.time() - started:.1f}s",
                    log_handle,
                )

    flat_rows: list[dict[str, Any]] = []
    for rec in records:
        base = {
            "file": rec["file"],
            "n_row_groups_in_file": rec["n_row_groups"],
            "n_rows_in_file": rec["n_rows"],
            "first_drug_in_file": rec["first_drug"],
            "last_drug_in_file": rec["last_drug"],
            "scan_status": rec["status"],
            "scan_error": rec["error"],
        }
        if rec["matched_row_groups"]:
            for match in rec["matched_row_groups"]:
                row = dict(base)
                row["row_group"] = match["row_group"]
                row["row_group_drug_min"] = match["drug_stat_min"]
                row["row_group_drug_max"] = match["drug_stat_max"]
                row["row_group_matched"] = True
                row["row_group_ambiguous_target_range"] = False
                row["row_group_match_mode"] = "exact_drug_stat"
                flat_rows.append(row)
        if rec["ambiguous_row_groups"]:
            for match in rec["ambiguous_row_groups"]:
                row = dict(base)
                row["row_group"] = match["row_group"]
                row["row_group_drug_min"] = match["drug_stat_min"]
                row["row_group_drug_max"] = match["drug_stat_max"]
                row["row_group_matched"] = False
                row["row_group_ambiguous_target_range"] = True
                row["row_group_match_mode"] = "ambiguous_drug_stat_range_not_scored"
                flat_rows.append(row)
        if not rec["matched_row_groups"] and not rec["ambiguous_row_groups"]:
            row = dict(base)
            row["row_group"] = np.nan
            row["row_group_drug_min"] = np.nan
            row["row_group_drug_max"] = np.nan
            row["row_group_matched"] = False
            row["row_group_ambiguous_target_range"] = False
            row["row_group_match_mode"] = "no_candidate_drug_stat"
            flat_rows.append(row)

    idx = pd.DataFrame(flat_rows)
    idx = idx.sort_values(["file", "row_group"], na_position="last").reset_index(drop=True)
    return idx


def init_accumulator() -> dict[str, Any]:
    return {
        "sum_weighted_contribution": 0.0,
        "sum_abs_weight": 0.0,
        "sum_abs_contribution": 0.0,
        "max_abs_contribution": 0.0,
        "positive_direction_genes": 0,
        "gene_set": set(),
        "up_gene_set": set(),
        "down_gene_set": set(),
        "sum_up_log2fc": 0.0,
        "sum_down_log2fc": 0.0,
        "n_rows_seen": 0,
        "n_cells_trt": np.nan,
        "n_cells_ctrl": np.nan,
        "top_contributions": [],
        "source_files": set(),
        "source_row_groups": set(),
    }


def add_top_contribution(acc: dict[str, Any], gene: str, contribution: float) -> None:
    vals = acc["top_contributions"]
    vals.append((gene, contribution))
    if len(vals) > 20:
        vals.sort(key=lambda x: abs(x[1]), reverse=True)
        del vals[10:]


def update_accumulators(
    df: pd.DataFrame,
    accs: dict[tuple[Any, ...], dict[str, Any]],
    weights: dict[str, float],
    up_genes: set[str],
    down_genes: set[str],
    variant_to_parent: dict[str, str],
    source_file: str,
    source_row_groups: list[int],
) -> None:
    if df.empty:
        return
    needed = [
        "gene_name",
        "log2FoldChange",
        "plate",
        "n_cells_trt",
        "n_cells_ctrl",
        "Cell_ID_Cellosaur",
        "Cell_ID_DepMap",
        "drug",
        "concentration",
        "concentration_unit",
        "Cell_Name_Vevo",
    ]
    present = [c for c in needed if c in df.columns]
    df = df[present].copy()
    df = df[df["drug"].isin(variant_to_parent)]
    df = df[df["gene_name"].isin(weights)]
    df = df.dropna(subset=["log2FoldChange", "gene_name", "drug"])
    if df.empty:
        return
    df["weight"] = df["gene_name"].map(weights).astype(float)
    df["log2FoldChange"] = df["log2FoldChange"].astype(float)
    df["contribution"] = df["weight"] * df["log2FoldChange"]
    df["abs_contribution"] = df["contribution"].abs()
    df["signed_positive"] = df["contribution"] > 0
    df["is_up_query"] = df["gene_name"].isin(up_genes)
    df["is_down_query"] = df["gene_name"].isin(down_genes)
    df["parent_drug"] = df["drug"].map(variant_to_parent)

    key_cols = [
        "parent_drug",
        "drug",
        "Cell_ID_DepMap",
        "Cell_ID_Cellosaur",
        "Cell_Name_Vevo",
        "plate",
        "concentration",
        "concentration_unit",
    ]
    for key, sub in df.groupby(key_cols, dropna=False, sort=False):
        acc = accs.setdefault(tuple(key), init_accumulator())
        acc["sum_weighted_contribution"] += float(sub["contribution"].sum())
        acc["sum_abs_weight"] += float(sub["weight"].abs().sum())
        acc["sum_abs_contribution"] += float(sub["abs_contribution"].sum())
        max_abs = float(sub["abs_contribution"].max()) if len(sub) else 0.0
        acc["max_abs_contribution"] = max(acc["max_abs_contribution"], max_abs)
        acc["positive_direction_genes"] += int(sub["signed_positive"].sum())
        up = sub[sub["is_up_query"]]
        down = sub[sub["is_down_query"]]
        acc["gene_set"].update(sub["gene_name"].dropna().astype(str).tolist())
        acc["up_gene_set"].update(up["gene_name"].dropna().astype(str).tolist())
        acc["down_gene_set"].update(down["gene_name"].dropna().astype(str).tolist())
        acc["sum_up_log2fc"] += float(up["log2FoldChange"].sum())
        acc["sum_down_log2fc"] += float(down["log2FoldChange"].sum())
        acc["n_rows_seen"] += len(sub)
        acc["source_files"].add(source_file)
        acc["source_row_groups"].update(f"{source_file}#rg{rg}" for rg in source_row_groups)
        if "n_cells_trt" in sub.columns:
            vals = sub["n_cells_trt"].dropna().unique()
            if len(vals):
                acc["n_cells_trt"] = float(vals[0])
        if "n_cells_ctrl" in sub.columns:
            vals = sub["n_cells_ctrl"].dropna().unique()
            if len(vals):
                acc["n_cells_ctrl"] = float(vals[0])
        top = sub.nlargest(min(10, len(sub)), "abs_contribution")
        for _, r in top.iterrows():
            add_top_contribution(acc, str(r["gene_name"]), float(r["contribution"]))


def read_one_file_row_groups(
    repo_path: str,
    row_groups: list[int],
    columns: list[str],
    max_retries: int = 2,
) -> pd.DataFrame:
    tmp_parent = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
    try:
        tmp_parent.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        tmp_parent = Path(tempfile.gettempdir())
    for attempt in range(max_retries + 1):
        try:
            with tempfile.TemporaryDirectory(prefix="tahoe_rg_", dir=tmp_parent) as tmpdir:
                local_path = hf_hub_download(DATASET_ID, repo_path, repo_type="dataset", local_dir=tmpdir)
                pf = pq.ParquetFile(local_path)
                table = pf.read_row_groups(row_groups, columns=columns, use_threads=True)
                return table.to_pandas()
        except Exception:  # noqa: BLE001
            if attempt < max_retries:
                time.sleep(2 + attempt)
            else:
                raise
    raise RuntimeError("unreachable")


def read_and_score_row_groups(
    index: pd.DataFrame,
    weights: dict[str, float],
    up_genes: set[str],
    down_genes: set[str],
    variant_to_parent: dict[str, str],
    workers: int,
    log_handle: Any | None,
    max_read_files: int | None = None,
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], list[dict[str, Any]]]:
    matched = index[index["row_group_matched"]].copy()
    matched = matched.dropna(subset=["row_group"])
    if matched.empty:
        return {}, []
    matched["row_group"] = matched["row_group"].astype(int)
    if max_read_files is not None:
        selected_files = sorted(matched["file"].unique())[:max_read_files]
        matched = matched[matched["file"].isin(selected_files)].copy()
        log(
            f"Applying max_read_files={max_read_files}; selected {matched['file'].nunique()} files and {len(matched)} exact row groups for scoring.",
            log_handle,
        )
    file_groups = [
        (file, sorted(sub["row_group"].tolist()))
        for file, sub in matched.groupby("file", sort=True)
    ]
    columns = [
        "gene_name",
        "log2FoldChange",
        "plate",
        "n_cells_trt",
        "n_cells_ctrl",
        "Cell_ID_Cellosaur",
        "Cell_ID_DepMap",
        "drug",
        "concentration",
        "concentration_unit",
        "Cell_Name_Vevo",
    ]

    accs: dict[tuple[Any, ...], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    done = 0
    started = time.time()

    def task(file: str, groups: list[int]) -> tuple[str, list[int], pd.DataFrame | None, str]:
        try:
            df = read_one_file_row_groups(file, groups, columns=columns)
            return file, groups, df, ""
        except Exception as exc:  # noqa: BLE001
            return file, groups, None, traceback.format_exc(limit=4)

    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_file = {
            pool.submit(task, file, groups): (file, groups) for file, groups in file_groups
        }
        for fut in futures.as_completed(future_to_file):
            file, groups, df, err = fut.result()
            done += 1
            if err:
                failures.append({"file": file, "n_row_groups": len(groups), "error": err})
            elif df is not None:
                update_accumulators(
                    df,
                    accs,
                    weights,
                    up_genes,
                    down_genes,
                    variant_to_parent,
                    file,
                    groups,
                )
            if done == 1 or done % 10 == 0 or done == len(file_groups):
                log(
                    f"row-group read progress {done}/{len(file_groups)} files; conditions={len(accs)}; failures={len(failures)}; elapsed={time.time() - started:.1f}s",
                    log_handle,
                )
    return accs, failures


def finalize_condition_scores(
    accs: dict[tuple[Any, ...], dict[str, Any]],
    ruler: pd.DataFrame,
    drug_meta: pd.DataFrame,
    cell_meta: pd.DataFrame,
) -> pd.DataFrame:
    n_ruler = int(ruler["gene"].nunique())
    total_abs_weight = float(ruler["consensus_z"].abs().sum())
    rows: list[dict[str, Any]] = []
    key_cols = [
        "parent_drug",
        "tahoe_drug_variant",
        "Cell_ID_DepMap",
        "Cell_ID_Cellosaur",
        "Cell_Name_Vevo",
        "plate",
        "concentration",
        "concentration_unit",
    ]
    for key, acc in accs.items():
        row = dict(zip(key_cols, key))
        n_genes_overlap = len(acc["gene_set"])
        n_up = len(acc["up_gene_set"])
        n_down = len(acc["down_gene_set"])
        weighted_score = (
            acc["sum_weighted_contribution"] / acc["sum_abs_weight"]
            if acc["sum_abs_weight"]
            else np.nan
        )
        query_score = np.nan
        if n_up > 0 and n_down > 0:
            query_score = (acc["sum_up_log2fc"] / n_up) - (acc["sum_down_log2fc"] / n_down)
        max_fraction = (
            acc["max_abs_contribution"] / acc["sum_abs_contribution"]
            if acc["sum_abs_contribution"]
            else np.nan
        )
        coverage_fraction = n_genes_overlap / n_ruler if n_ruler else np.nan
        effective_weight_coverage = acc["sum_abs_weight"] / total_abs_weight if total_abs_weight else np.nan
        directional_fraction = (
            acc["positive_direction_genes"] / acc["n_rows_seen"]
            if acc["n_rows_seen"]
            else np.nan
        )
        top_vals = sorted(acc["top_contributions"], key=lambda x: abs(x[1]), reverse=True)[:10]
        row.update(
            {
                "raw_drug": row["tahoe_drug_variant"],
                "term": row["parent_drug"],
                "source_priority": "DrugReflector/L1000 candidate covered in Tahoe-100M",
                "plate_normalized": f"plate{str(row['plate']).replace('plate', '')}",
                "weighted_projection_score": weighted_score,
                "query_direction_score": query_score,
                "directional_fraction": directional_fraction,
                "n_genes_overlap": n_genes_overlap,
                "n_ruler_genes": n_ruler,
                "coverage_fraction": coverage_fraction,
                "effective_weight_coverage": effective_weight_coverage,
                "n_up_detected": n_up,
                "n_down_detected": n_down,
                "n_query_up_total": 150,
                "n_query_down_total": 150,
                "n_cells_trt": acc["n_cells_trt"],
                "n_cells_ctrl": acc["n_cells_ctrl"],
                "dmso_match_status": "pseudobulk_has_DMSO_TF_control_count"
                if pd.notna(acc["n_cells_ctrl"]) and acc["n_cells_ctrl"] > 0
                else "missing_control_count",
                "gene_row_count": acc["n_rows_seen"],
                "n_source_files": len(acc["source_files"]),
                "n_source_row_groups": len(acc["source_row_groups"]),
                "source_files": ";".join(sorted(acc["source_files"])),
                "row_group_index": ";".join(sorted(acc["source_row_groups"])),
                "max_single_gene_abs_contribution_fraction": max_fraction,
                "top10_gene_contributions": ";".join(f"{g}:{v:.5g}" for g, v in top_vals),
                "score_definition": "sum(consensus_z * Tahoe log2FC) / sum(abs(consensus_z)); positive values indicate CHK1i-sensitive-like direction",
                "score_layer": "Tahoe-100M pseudobulk_differential_expression",
                "source_data": "tahoebio/Tahoe-100M pseudobulk_differential_expression",
                "source_version": SOURCE_VERSION,
                "claim_boundary": "Exploratory state-similarity score; not CHK1i synergy, rescue, or causal validation.",
                "interpretation_boundary": "Drug-treated versus Tahoe plate-matched DMSO_TF pseudobulk direction projected onto the CHK1i-sensitive ruler.",
            }
        )
        downgrade: list[str] = []
        if pd.isna(row["n_cells_trt"]) or row["n_cells_trt"] < 50:
            downgrade.append("low_treated_cell_count")
        if pd.isna(row["n_cells_ctrl"]) or row["n_cells_ctrl"] < 50:
            downgrade.append("low_control_cell_count")
        if coverage_fraction < 0.60:
            downgrade.append("low_ruler_gene_coverage")
        if effective_weight_coverage < 0.60:
            downgrade.append("low_effective_weight_coverage")
        if n_up < 90:
            downgrade.append("low_query_up_coverage")
        if n_down < 90:
            downgrade.append("low_query_down_coverage")
        if not downgrade:
            row["gate"] = "PASS"
            row["downgrade_reason"] = ""
        else:
            row["gate"] = "WARN"
            row["downgrade_reason"] = ";".join(downgrade)
        rows.append(row)
    scores = pd.DataFrame(rows)
    if scores.empty:
        return scores

    drug_cols = [
        "drug",
        "targets",
        "moa_broad",
        "moa_fine",
        "human_approved",
        "clinical_trials",
        "canonical_smiles",
        "pubchem_cid",
    ]
    scores = scores.merge(
        drug_meta[[c for c in drug_cols if c in drug_meta.columns]].rename(columns={"drug": "tahoe_drug_variant"}),
        on="tahoe_drug_variant",
        how="left",
    )
    scores = scores.merge(cell_meta, on="Cell_ID_DepMap", how="left")
    scores = scores.sort_values(
        ["weighted_projection_score", "query_direction_score"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)
    return scores


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    vals = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce")
    mask = vals.notna() & w.notna() & (w > 0)
    if not mask.any():
        return float(vals.mean())
    return float(np.average(vals[mask], weights=w[mask]))


def leave_one_min_score(df: pd.DataFrame, group_col: str, score_col: str, weight_col: str) -> float:
    groups = [g for g in df[group_col].dropna().unique()]
    if len(groups) < 2:
        return np.nan
    vals = []
    for group in groups:
        sub = df[df[group_col] != group]
        if not sub.empty:
            vals.append(weighted_mean(sub[score_col], sub[weight_col]))
    return float(np.min(vals)) if vals else np.nan


def summarize(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if scores.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    scores = scores.copy()
    scores["condition_weight"] = (
        pd.to_numeric(scores["n_cells_trt"], errors="coerce")
        .clip(lower=1)
        .fillna(1)
        .combine(
            pd.to_numeric(scores["n_cells_ctrl"], errors="coerce").clip(lower=1).fillna(1),
            min,
        )
        * pd.to_numeric(scores["coverage_fraction"], errors="coerce").fillna(0)
    )
    pass_scores = scores[scores["gate"].isin(["PASS", "WARN"])].copy()

    parent_rows: list[dict[str, Any]] = []
    for parent, sub in pass_scores.groupby("parent_drug", dropna=False):
        by_cell = sub.groupby("Cell_ID_DepMap")["condition_weight"].sum()
        dominant_cell = float(by_cell.max() / by_cell.sum()) if by_cell.sum() else np.nan
        mean_score = weighted_mean(sub["weighted_projection_score"], sub["condition_weight"])
        parent_rows.append(
            {
                "parent_drug": parent,
                "n_conditions": len(sub),
                "n_tahoe_variants": sub["tahoe_drug_variant"].nunique(),
                "n_cell_lines": sub["Cell_ID_DepMap"].nunique(),
                "n_organs": sub["Organ"].nunique(),
                "weighted_mean_projection_score": mean_score,
                "median_projection_score": float(sub["weighted_projection_score"].median()),
                "max_projection_score": float(sub["weighted_projection_score"].max()),
                "positive_fraction": float((sub["weighted_projection_score"] > 0).mean()),
                "dominant_cell_line_fraction": dominant_cell,
                "leave_one_cell_line_min_score": leave_one_min_score(
                    sub, "Cell_ID_DepMap", "weighted_projection_score", "condition_weight"
                ),
                "best_cell_line": sub.iloc[0]["Cell_ID_DepMap"] if len(sub) else "",
                "best_organ": sub.iloc[0].get("Organ", ""),
                "moa_fine_values": ";".join(sorted(set(sub["moa_fine"].dropna().astype(str)))),
                "claim_boundary": "Parent-drug state-similarity summary; not functional CHK1i sensitization.",
            }
        )
    parent_summary = pd.DataFrame(parent_rows)
    if not parent_summary.empty:
        parent_summary["gate"] = np.where(
            (parent_summary["n_conditions"] >= 3)
            & (parent_summary["n_cell_lines"] >= 2)
            & (parent_summary["positive_fraction"] >= 0.60)
            & (parent_summary["weighted_mean_projection_score"] > 0)
            & (parent_summary["dominant_cell_line_fraction"] <= 0.60),
            "PASS",
            "WARN",
        )
        parent_summary["downgrade_reason"] = parent_summary.apply(parent_downgrade_reason, axis=1)
        parent_summary = parent_summary.sort_values(
            ["weighted_mean_projection_score", "positive_fraction"],
            ascending=[False, False],
        ).reset_index(drop=True)

    moa_rows: list[dict[str, Any]] = []
    moa_field = "moa_fine"
    pass_scores[moa_field] = pass_scores[moa_field].fillna("unannotated")
    for moa, sub in pass_scores.groupby(moa_field, dropna=False):
        by_parent = sub.groupby("parent_drug")["condition_weight"].sum()
        by_cell = sub.groupby("Cell_ID_DepMap")["condition_weight"].sum()
        total_parent_weight = by_parent.sum()
        total_cell_weight = by_cell.sum()
        dominant_parent = float(by_parent.max() / total_parent_weight) if total_parent_weight else np.nan
        dominant_cell = float(by_cell.max() / total_cell_weight) if total_cell_weight else np.nan
        moa_rows.append(
            {
                "moa_fine": moa,
                "n_parent_drugs": sub["parent_drug"].nunique(),
                "parent_drugs": ";".join(sorted(set(sub["parent_drug"].dropna().astype(str)))),
                "n_conditions": len(sub),
                "n_cell_lines": sub["Cell_ID_DepMap"].nunique(),
                "n_organs": sub["Organ"].nunique(),
                "weighted_mean_projection_score": weighted_mean(
                    sub["weighted_projection_score"], sub["condition_weight"]
                ),
                "median_projection_score": float(sub["weighted_projection_score"].median()),
                "positive_fraction": float((sub["weighted_projection_score"] > 0).mean()),
                "dominant_parent_drug_fraction": dominant_parent,
                "dominant_cell_line_fraction": dominant_cell,
                "leave_one_parent_min_score": leave_one_min_score(
                    sub, "parent_drug", "weighted_projection_score", "condition_weight"
                ),
                "leave_one_cell_line_min_score": leave_one_min_score(
                    sub, "Cell_ID_DepMap", "weighted_projection_score", "condition_weight"
                ),
                "claim_boundary": "MoA class convergence for CHK1i-sensitive-like state; not combination efficacy validation.",
            }
        )
    moa_summary = pd.DataFrame(moa_rows)
    if not moa_summary.empty:
        moa_summary["gate"] = np.where(
            (moa_summary["n_parent_drugs"] >= 2)
            & (moa_summary["n_cell_lines"] >= 2)
            & (moa_summary["positive_fraction"] >= 0.60)
            & (moa_summary["weighted_mean_projection_score"] > 0)
            & (moa_summary["dominant_parent_drug_fraction"] <= 0.60)
            & (moa_summary["dominant_cell_line_fraction"] <= 0.60),
            "PASS",
            "WARN",
        )
        moa_summary["downgrade_reason"] = moa_summary.apply(moa_downgrade_reason, axis=1)
        moa_summary = moa_summary.sort_values(
            ["weighted_mean_projection_score", "positive_fraction"],
            ascending=[False, False],
        ).reset_index(drop=True)

    organ_rows: list[dict[str, Any]] = []
    for organ, sub in pass_scores.groupby("Organ", dropna=False):
        organ_rows.append(
            {
                "Organ": organ,
                "n_parent_drugs": sub["parent_drug"].nunique(),
                "n_conditions": len(sub),
                "n_cell_lines": sub["Cell_ID_DepMap"].nunique(),
                "weighted_mean_projection_score": weighted_mean(
                    sub["weighted_projection_score"], sub["condition_weight"]
                ),
                "positive_fraction": float((sub["weighted_projection_score"] > 0).mean()),
                "top_parent_drugs": ";".join(
                    sub.groupby("parent_drug")["weighted_projection_score"]
                    .mean()
                    .sort_values(ascending=False)
                    .head(5)
                    .index.astype(str)
                ),
                "claim_boundary": "Organ-stratified state-similarity pattern; prioritizes experimental models only.",
            }
        )
    organ_summary = pd.DataFrame(organ_rows)
    if not organ_summary.empty:
        organ_summary = organ_summary.sort_values(
            ["weighted_mean_projection_score", "positive_fraction"],
            ascending=[False, False],
        ).reset_index(drop=True)

    return parent_summary, moa_summary, organ_summary


def parent_downgrade_reason(row: pd.Series) -> str:
    reasons = []
    if row["n_conditions"] < 3:
        reasons.append("few_conditions")
    if row["n_cell_lines"] < 2:
        reasons.append("few_cell_lines")
    if row["positive_fraction"] < 0.60:
        reasons.append("low_positive_fraction")
    if row["weighted_mean_projection_score"] <= 0:
        reasons.append("non_positive_mean_score")
    if row["dominant_cell_line_fraction"] > 0.60:
        reasons.append("single_cell_line_dominant")
    return ";".join(reasons)


def moa_downgrade_reason(row: pd.Series) -> str:
    reasons = []
    if row["n_parent_drugs"] < 2:
        reasons.append("single_parent_drug_moa")
    if row["n_cell_lines"] < 2:
        reasons.append("few_cell_lines")
    if row["positive_fraction"] < 0.60:
        reasons.append("low_positive_fraction")
    if row["weighted_mean_projection_score"] <= 0:
        reasons.append("non_positive_mean_score")
    if row["dominant_parent_drug_fraction"] > 0.60:
        reasons.append("single_parent_drug_dominant")
    if row["dominant_cell_line_fraction"] > 0.60:
        reasons.append("single_cell_line_dominant")
    return ";".join(reasons)


def save_outputs(
    manifest: pd.DataFrame,
    sample_subset: pd.DataFrame,
    index: pd.DataFrame,
    scores: pd.DataFrame,
    parent_summary: pd.DataFrame,
    moa_summary: pd.DataFrame,
    organ_summary: pd.DataFrame,
    failures: list[dict[str, Any]],
    args: argparse.Namespace,
    runtime_seconds: float,
) -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(TABLE_DIR / "tahoe_candidate_drug_manifest.tsv", sep="\t", index=False)
    sample_subset.to_csv(TABLE_DIR / "tahoe_candidate_sample_metadata_rows.tsv", sep="\t", index=False)
    index.to_csv(TABLE_DIR / "tahoe_pseudobulk_candidate_rowgroup_index.tsv", sep="\t", index=False)
    manifest_cols = [
        "raw_drug",
        "parent_drug",
        "term",
        "source_priority",
        "Cell_Name_Vevo",
        "Cell_ID_Cellosaur",
        "Cell_ID_DepMap",
        "Organ",
        "concentration",
        "concentration_unit",
        "plate",
        "plate_normalized",
        "source_files",
        "row_group_index",
        "n_cells_trt",
        "n_cells_ctrl",
        "dmso_match_status",
        "gene_row_count",
        "n_genes_overlap",
        "coverage_fraction",
        "gate",
        "downgrade_reason",
        "claim_boundary",
    ]
    if scores.empty:
        condition_manifest = pd.DataFrame(columns=manifest_cols)
    else:
        condition_manifest = scores[[c for c in manifest_cols if c in scores.columns]].copy()
    condition_manifest.to_csv(TABLE_DIR / "tahoe_condition_analysis_manifest.tsv", sep="\t", index=False)
    scores.to_csv(TABLE_DIR / "tahoe_pseudobulk_chk1i_projection_scores.tsv", sep="\t", index=False)
    parent_summary.to_csv(TABLE_DIR / "tahoe_pseudobulk_parent_drug_summary.tsv", sep="\t", index=False)
    moa_summary.to_csv(TABLE_DIR / "tahoe_pseudobulk_moa_summary.tsv", sep="\t", index=False)
    organ_summary.to_csv(TABLE_DIR / "tahoe_pseudobulk_organ_summary.tsv", sep="\t", index=False)
    pd.DataFrame(failures).to_csv(TABLE_DIR / "tahoe_pseudobulk_read_failures.tsv", sep="\t", index=False)

    qc = {
        "run_started_utc": args.run_started_utc,
        "runtime_seconds": runtime_seconds,
        "dataset_id": DATASET_ID,
        "source_data": "pseudobulk_differential_expression",
        "source_version": SOURCE_VERSION,
        "max_files": args.max_files,
        "index_only": args.index_only,
        "max_read_files": args.max_read_files,
        "footer_workers": args.footer_workers,
        "read_workers": args.read_workers,
        "n_candidate_parent_drugs": int(manifest["parent_drug"].nunique()),
        "n_candidate_tahoe_variants": int(manifest["tahoe_drug_variant"].nunique()),
        "n_sample_metadata_rows_for_candidates": int(len(sample_subset)),
        "n_scanned_files": int(index["file"].nunique()) if not index.empty else 0,
        "n_row_groups_matched": int(index["row_group_matched"].sum()) if not index.empty else 0,
        "n_ambiguous_range_row_groups": int(index["row_group_ambiguous_target_range"].sum()) if "row_group_ambiguous_target_range" in index.columns else 0,
        "n_files_with_matched_row_groups": int(index[index["row_group_matched"]]["file"].nunique()) if not index.empty else 0,
        "n_condition_scores": int(len(scores)),
        "n_parent_summaries": int(len(parent_summary)),
        "n_moa_summaries": int(len(moa_summary)),
        "n_organ_summaries": int(len(organ_summary)),
        "n_read_failures": int(len(failures)),
        "claim_boundary": "Tahoe pseudobulk projection supports exploratory state-similarity prioritization only.",
        "gate_rule_condition": "PASS requires n_cells_trt>=50, n_cells_ctrl>=50, coverage_fraction>=0.60, effective_weight_coverage>=0.60, n_up_detected>=90, n_down_detected>=90.",
        "gate_rule_moa": "PASS requires >=2 parent drugs, >=2 cell lines, positive_fraction>=0.60, weighted mean score>0, no dominant parent/cell line >0.60.",
    }
    with open(QC_DIR / "tahoe_pseudobulk_chk1i_projection_qc.json", "w") as handle:
        json.dump(qc, handle, indent=2, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-files", type=int, default=None, help="Optional first-N shard limit for pilot runs.")
    parser.add_argument("--footer-workers", type=int, default=24)
    parser.add_argument("--read-workers", type=int, default=6)
    parser.add_argument("--index-only", action="store_true", help="Scan and save row-group index without reading expression rows.")
    parser.add_argument("--max-read-files", type=int, default=None, help="Limit the number of exact-matched parquet files read for pilot scoring.")
    parser.add_argument("--reuse-index", action="store_true")
    parser.add_argument("--index-path", type=Path, default=TABLE_DIR / "tahoe_pseudobulk_candidate_rowgroup_index.tsv")
    args = parser.parse_args()
    args.run_started_utc = datetime.now(timezone.utc).isoformat()
    return args


def main() -> int:
    args = parse_args()
    start = time.time()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "run_tahoe_pseudobulk_chk1i_projection.log"
    with open(log_path, "a") as log_handle:
        log("=" * 80, log_handle)
        log(f"Starting Tahoe pseudobulk CHK1i projection; args={vars(args)}", log_handle)
        paths = Paths()
        manifest, variant_to_parent, target_variants = load_candidate_manifest(paths)
        drug_meta, cell_meta, sample_subset = load_metadata(paths, manifest)
        ruler, up_genes, down_genes, weights = load_ruler(paths)
        log(
            f"Loaded {manifest['parent_drug'].nunique()} parent drugs, {len(target_variants)} Tahoe variants, {len(ruler)} ruler genes.",
            log_handle,
        )

        if args.reuse_index and args.index_path.exists():
            index = pd.read_csv(args.index_path, sep="\t")
            log(f"Reused row-group index from {args.index_path}", log_handle)
        else:
            repo_paths = list_pseudobulk_files(args.max_files)
            log(f"Scanning {len(repo_paths)} pseudobulk shards for target drugs.", log_handle)
            index = scan_row_groups(repo_paths, target_variants, args.footer_workers, log_handle)

        n_matched = int(index["row_group_matched"].sum()) if not index.empty else 0
        log(f"Matched row groups: {n_matched}", log_handle)
        if args.index_only:
            runtime = time.time() - start
            empty = pd.DataFrame()
            save_outputs(
                manifest,
                sample_subset,
                index,
                empty,
                empty,
                empty,
                empty,
                [],
                args,
                runtime,
            )
            log(f"Index-only run saved row-group index; runtime={runtime:.1f}s", log_handle)
            return 0
        accs, failures = read_and_score_row_groups(
            index,
            weights,
            up_genes,
            down_genes,
            variant_to_parent,
            args.read_workers,
            log_handle,
            args.max_read_files,
        )
        log(f"Accumulated condition score entries: {len(accs)}", log_handle)
        scores = finalize_condition_scores(accs, ruler, drug_meta, cell_meta)
        parent_summary, moa_summary, organ_summary = summarize(scores)
        runtime = time.time() - start
        save_outputs(
            manifest,
            sample_subset,
            index,
            scores,
            parent_summary,
            moa_summary,
            organ_summary,
            failures,
            args,
            runtime,
        )
        log(f"Saved outputs to {TABLE_DIR} and {QC_DIR}; runtime={runtime:.1f}s", log_handle)
        if not scores.empty:
            top = scores[["parent_drug", "tahoe_drug_variant", "Cell_ID_DepMap", "Organ", "weighted_projection_score", "gate"]].head(10)
            log("Top condition scores:\n" + top.to_string(index=False), log_handle)
        if not moa_summary.empty:
            top_moa = moa_summary[["moa_fine", "n_parent_drugs", "n_conditions", "weighted_mean_projection_score", "positive_fraction", "gate"]].head(10)
            log("Top MoA summaries:\n" + top_moa.to_string(index=False), log_handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
