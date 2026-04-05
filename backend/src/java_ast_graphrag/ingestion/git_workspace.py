"""JAVA_MES_SOURCE_ROOT 가 로컬 경로 또는 Git 원격 URL일 때 → 수집용 로컬 디렉터리."""
from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_git_url(s: str) -> str:
    return str(s).strip().replace("\\", "/")


def is_git_remote_url(s: str) -> bool:
    t = normalize_git_url(s)
    if not t:
        return False
    return (
        t.startswith("http://")
        or t.startswith("https://")
        or t.startswith("git@")
        or t.endswith(".git")
    )


def _cache_base() -> Path:
    from config import BACKEND_ROOT, settings

    raw = getattr(settings, "JAVA_MES_GIT_CACHE_DIR", None)
    if raw and str(raw).strip():
        p = Path(str(raw).strip())
        if p.is_absolute():
            return p.resolve()
        return (BACKEND_ROOT / p).resolve()
    return (BACKEND_ROOT / ".cache" / "java_mes_repos").resolve()


def cache_dir_for_remote(url: str) -> Path:
    u = normalize_git_url(url)
    tail = u.rstrip("/").split("/")[-1].replace(".git", "") or "repo"
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", tail)[:64]
    h = hashlib.sha256(u.encode()).hexdigest()[:10]
    return _cache_base() / f"{safe}_{h}"


def ensure_git_checkout(url: str) -> Path:
    """원격 URL을 캐시 디렉터리에 clone 또는 pull."""
    from config import settings

    u = normalize_git_url(url)
    dest = cache_dir_for_remote(u)
    dest.parent.mkdir(parents=True, exist_ok=True)

    shallow = bool(getattr(settings, "JAVA_MES_GIT_SHALLOW", True))
    branch = getattr(settings, "JAVA_MES_GIT_BRANCH", None)
    branch_s = str(branch).strip() if branch else ""

    if dest.exists() and not (dest / ".git").is_dir():
        raise FileExistsError(
            f"캐시 경로에 Git 저장소가 아닌 항목이 있습니다: {dest}. 삭제하거나 JAVA_MES_GIT_CACHE_DIR을 바꾸세요.",
        )

    if (dest / ".git").is_dir():
        logger.info("기존 저장소 갱신: %s", dest)
        subprocess.run(
            ["git", "-C", str(dest), "fetch", "--all"],
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(dest), "pull", "--ff-only"],
            check=False,
            capture_output=True,
            text=True,
        )
        return dest.resolve()

    clone_cmd: list[str] = ["git", "clone"]
    if shallow:
        clone_cmd.extend(["--depth", "1"])
    if branch_s:
        clone_cmd.extend(["-b", branch_s])
    clone_cmd.extend([u, str(dest)])

    logger.info("git clone → %s", dest)
    r = subprocess.run(clone_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"git clone 실패 (git 설치 및 네트워크 확인): {r.stderr or r.stdout or r.returncode}",
        )
    return dest.resolve()


def resolve_java_mes_root(raw: str) -> Path:
    """로컬 경로이면 그대로, Git 원격이면 clone 후 캐시 경로."""
    from config import resolve_backend_path

    s = str(raw).strip()
    if not s:
        raise ValueError("JAVA_MES_SOURCE_ROOT / root 가 비어 있습니다.")

    if is_git_remote_url(s):
        return ensure_git_checkout(s)

    resolved = resolve_backend_path(s) or s
    return Path(resolved).resolve()
