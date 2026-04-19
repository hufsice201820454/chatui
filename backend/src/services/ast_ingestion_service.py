"""Service wrapper for embedded ast_graphdb ingestion pipeline."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AST_GRAPHDB_ROOT = Path(__file__).resolve().parents[2] / "ast_graphdb"


def run_ast_ingestion() -> dict:
    """Run ast_graphdb ingestion as a subprocess and return normalized result."""
    cmd = [sys.executable, "-m", "ingestion.main"]
    proc = subprocess.run(
        cmd,
        cwd=str(AST_GRAPHDB_ROOT),
        capture_output=True,
        text=False,
    )
    stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    return {
        "success": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
        "cwd": str(AST_GRAPHDB_ROOT),
        "command": " ".join(cmd),
    }
