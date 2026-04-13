from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.java_ast_graphrag.ingestion.pipeline import run_ingestion


def main() -> int:
    parser = argparse.ArgumentParser(description="Java AST GraphRAG ingestion runner")
    parser.add_argument("--root", type=str, default=None, help="Local path or git URL")
    parser.add_argument("--dry-run", action="store_true", help="Parse/resolve only without Neo4j write")
    parser.add_argument("--json", action="store_true", help="Print report as JSON")
    args = parser.parse_args()

    rep = asyncio.run(run_ingestion(args.root, dry_run=args.dry_run))
    if args.json:
        print(
            json.dumps(
                {
                    "root": rep.root,
                    "files_seen": rep.files_seen,
                    "files_parsed_ok": rep.files_parsed_ok,
                    "files_failed": rep.files_failed,
                    "classes_upserted": rep.classes_upserted,
                    "methods_upserted": rep.methods_upserted,
                    "calls_merged": rep.calls_merged,
                    "errors": rep.errors[:20],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"root={rep.root}")
        print(f"files={rep.files_seen} ok={rep.files_parsed_ok} failed={rep.files_failed}")
        print(
            f"upserts classes={rep.classes_upserted} "
            f"methods={rep.methods_upserted} calls={rep.calls_merged}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

