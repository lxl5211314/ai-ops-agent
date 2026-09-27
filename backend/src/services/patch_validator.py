import shutil
import subprocess
import tempfile
from pathlib import Path


def validate_patch(project_dir: str | Path, patch_text: str) -> tuple[bool, str]:
    """Dry-run the patch on a copy of the project. Returns (applicable, log)."""
    src = Path(project_dir)
    if not src.exists() or not patch_text.strip():
        return False, "项目目录不存在或补丁为空"
    tmp = Path(tempfile.mkdtemp(prefix="patchcheck_"))
    try:
        copy_root = tmp / "proj"
        shutil.copytree(src, copy_root, symlinks=True)
        patch_file = tmp / "fix.patch"
        patch_file.write_bytes(patch_text.encode("utf-8"))

        git_ok, git_log = _run(["git", "apply", "--check", str(patch_file)], copy_root)
        if git_ok:
            return True, git_log or "git apply --check passed"

        patch_alt = _run(["patch", "-p1", "--dry-run", "-i", str(patch_file)], copy_root)
        if patch_alt[0]:
            return True, patch_alt[1] or "patch --dry-run passed"

        return False, (git_log + "\n" + patch_alt[1]).strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError:
        return False, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, "patch validation timed out"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out.strip()[:4000]
