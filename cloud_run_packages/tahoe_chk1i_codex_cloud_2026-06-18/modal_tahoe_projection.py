"""Optional Modal launcher for the Tahoe CHK1i projection package.

This file is not required for Codex Cloud. It is provided so the same package
can be run on Modal after `modal token new` has configured credentials.
"""

import modal

app = modal.App("tahoe-chk1i-sensitive-state-projection")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("tar")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir(".", remote_path="/workspace")
)

volume = modal.Volume.from_name("tahoe-chk1i-projection", create_if_missing=True)


@app.function(
    image=image,
    volumes={"/outputs": volume},
    cpu=8.0,
    memory=32768,
    ephemeral_disk=200000,
    timeout=24 * 60 * 60,
)
def run_full_projection() -> str:
    import os
    import shutil
    import subprocess
    from pathlib import Path

    work = Path("/tmp/tahoe_chk1i_cloud_run")
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree("/workspace", work)
    env = os.environ.copy()
    env["PROJECT_ROOT"] = str(work)
    env["RESULT_ROOT"] = str(work / "results/pancancer_chk1i_sensitizer_2026-06-17")
    env["HF_HOME"] = "/tmp/hf_cache"
    subprocess.run(["bash", "run_full_tahoe_projection.sh"], cwd=work, env=env, check=True)
    out = work / "tahoe_chk1i_projection_outputs.tar.gz"
    target = Path("/outputs/tahoe_chk1i_projection_outputs.tar.gz")
    shutil.copy2(out, target)
    volume.commit()
    return str(target)


@app.local_entrypoint()
def main() -> None:
    print(run_full_projection.remote())
