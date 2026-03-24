# Input & Environment Report

## Phase 1 checks
- Working directory: `/workspace/20260324`
- OS/kernel: Ubuntu 24.04.3 LTS, Linux x86_64.
- Python/pip/git available: Python 3.10.19, pip 25.3, git 2.43.0.
- GPU check: `nvidia-smi` not found (no visible NVIDIA GPU tooling in this container).
- Disk: root filesystem ~63G total, ~34G available at check time.
- Network: outbound HTTPS works (GitHub reachable), but Hugging Face API access is blocked by proxy (`403 Forbidden`).

## Input file existence/readability
- `AML_D0_for_State_beginner.h5ad` exists and is readable.
- HDF5 signature check passed (`\x89HDF\r\n\x1a\n`).

## Compatibility note
- Original file contains `uns/log1p/base` with `encoding-type='null'`, which fails direct `anndata.read_h5ad` in this environment.
- Created a cleaned analysis copy: `AML_D0_for_State_beginner_clean.h5ad` by removing `uns/log1p/base` only.
