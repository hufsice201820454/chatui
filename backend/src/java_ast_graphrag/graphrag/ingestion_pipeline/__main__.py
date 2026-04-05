"""python -m src.java_ast_graphrag.graphrag.ingestion_pipeline [--root PATH] [--dry-run]"""
from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    p = argparse.ArgumentParser(description="Java 소스 → Neo4j 적재 (java_ast_graphrag)")
    p.add_argument(
        "--root",
        type=str,
        default=None,
        help="Java 프로젝트 루트 (기본: JAVA_MES_SOURCE_ROOT)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Neo4j에 쓰지 않고 파싱·통계만",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="결과를 JSON 한 줄로 stdout",
    )
    args = p.parse_args()

    from src.java_ast_graphrag.graphrag.ingestion_pipeline.pipeline import run_ingestion

    try:
        rep = run_ingestion(args.root, dry_run=args.dry_run)
    except Exception as e:
        logging.error("%s", e)
        return 1

    if args.json:
        d = {
            "dry_run": rep.dry_run,
            "root": rep.root,
            "files_seen": rep.files_seen,
            "files_parsed_ok": rep.files_parsed_ok,
            "files_failed": rep.files_failed,
            "classes_upserted": rep.classes_upserted,
            "methods_upserted": rep.methods_upserted,
            "calls_merged": rep.calls_merged,
            "errors": rep.errors[:50],
        }
        print(json.dumps(d, ensure_ascii=False))
    else:
        print(f"root={rep.root} dry_run={rep.dry_run}")
        print(
            f"files: {rep.files_seen} ok={rep.files_parsed_ok} failed={rep.files_failed}",
        )
        print(
            f"upserts: classes={rep.classes_upserted} methods={rep.methods_upserted} calls={rep.calls_merged}",
        )
        for e in rep.errors[:20]:
            print(f"  ERR {e}")
        if len(rep.errors) > 20:
            print(f"  ... +{len(rep.errors) - 20} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
