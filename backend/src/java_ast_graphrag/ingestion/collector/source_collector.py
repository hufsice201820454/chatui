from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess

from config import BACKEND_ROOT

@dataclass
class JavaSourceFile:
    relative_path: str
    content: str


def _cache_repo_dir(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    stem = url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "") or "repo"
    return (BACKEND_ROOT / ".cache" / "java_mes_repos" / f"{stem}_{digest}").resolve()


def _ensure_repo(url: str) -> Path:
    repo_dir = _cache_repo_dir(url)
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if not repo_dir.exists():
        subprocess.run(["git", "clone", "--depth", "1", url, str(repo_dir)], check=True)
    else:
        subprocess.run(["git", "-C", str(repo_dir), "fetch", "--depth", "1", "origin"], check=False)
        subprocess.run(["git", "-C", str(repo_dir), "reset", "--hard", "origin/HEAD"], check=False)
    return repo_dir


def resolve_source_root(root: str | Path) -> Path:
    s = str(root).strip()
    if s.startswith("http://") or s.startswith("https://") or s.endswith(".git"):
        return _ensure_repo(s)
    return Path(s).resolve()


def collect_java_sources(root: str | Path) -> list[JavaSourceFile]:
    root_path = resolve_source_root(root)
    if not root_path.exists():
        raise FileNotFoundError(f"Java source root not found: {root_path}")

    out: list[JavaSourceFile] = []
    for p in sorted(root_path.rglob("*.java")):
        if not p.is_file():
            continue
        rel = p.relative_to(root_path).as_posix()
        out.append(JavaSourceFile(relative_path=rel, content=p.read_text(encoding="utf-8", errors="ignore")))
    return out

