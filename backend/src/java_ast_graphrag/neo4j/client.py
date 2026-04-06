"""Neo4j 드라이버 싱글톤 (lazy)."""
from __future__ import annotations
 
import logging
import threading
from collections.abc import Callable
from typing import Any, TypeVar
 
from config import neo4j_database_for_session, settings
 
logger = logging.getLogger(__name__)
 
# asyncio.to_thread 등 워커 스레드에서 메인 스레드가 만든 드라이버 풀을 쓰면 세션이 깨질 수 있어 스레드별 드라이버
_driver_tls = threading.local()
 
# Aura UUID 경고 중복 방지 (step마다 반복 출력 억제)
_warned_db_uuid: bool = False
 
T = TypeVar("T")
 
 
def neo4j_database_not_found(exc: BaseException) -> bool:
    """Aura: graph reference / Database ... not found 등."""
    code = getattr(exc, "code", None)
    if code and "DatabaseNotFound" in str(code):
        return True
    s = str(exc).lower()
    if "databasenotfound" in s or "database not found" in s:
        return True
    if "graph reference" in s and "not found" in s:
        return True
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        return neo4j_database_not_found(cause)
    return False
 
 
def _discover_graph_database_names(driver: Any) -> list[str]:
    """system DB에서 온라인 사용자 DB 이름 (SHOW DATABASES 만 사용)."""
    ordered: list[str] = []
    seen: set[str] = set()
 
    def add(name: str | None) -> None:
        if not name or name == "system" or name in seen:
            return
        seen.add(name)
        ordered.append(name)
 
    try:
        with driver.session(database="system") as session:
            try:
                rows = session.run(
                    "SHOW DATABASES YIELD name, currentStatus "
                    "WHERE name <> 'system' AND currentStatus = 'online' "
                    "RETURN name ORDER BY name",
                )
                for r in rows:
                    add(r.get("name"))
                if not ordered:
                    rows2 = session.run(
                        "SHOW DATABASES YIELD name WHERE name <> 'system' RETURN name ORDER BY name",
                    )
                    for r in rows2:
                        add(r.get("name"))
            except Exception as e:
                logger.debug("SHOW DATABASES 생략: %s", e)
    except Exception as e:
        logger.warning("Neo4j system 세션으로 DB 목록 조회 실패: %s", e)
    return ordered
 
 
def _is_aura_uuid(db_name: str) -> bool:
    """Aura 인스턴스 ID(8자리 hex 등) 여부 간단 판별."""
    import re
    return bool(re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){0,4}", db_name.strip(), re.I))
 
 
def iter_session_kwarg_candidates(driver: Any) -> list[dict[str, Any]]:
    """`driver.session(**kw)` 후보: 명시 DB → SHOW 목록 → 폴백 이름 → (Aura) 홈.
 
    NEO4J_DATABASE 를 하나만 쓰면 Bolt/GQL 이 graph reference not found 를 낼 때
    복구할 수 없어, 명시 값도 항상 같은 폴백 체인을 탄다.
    """
    global _warned_db_uuid
 
    explicit = neo4j_database_for_session()
 
    # Aura UUID 경고 — 최초 1회만 출력
    if explicit and _is_aura_uuid(explicit) and not _warned_db_uuid:
        logger.warning(
            "NEO4J_DATABASE='%s' 가 Aura 인스턴스 ID(UUID) 처럼 보입니다. "
            "Aura의 DB 이름은 보통 'neo4j' 입니다. 자동 탐색으로 전환합니다.",
            explicit,
        )
        _warned_db_uuid = True
 
    discovered = _discover_graph_database_names(driver)
    fb = (getattr(settings, "NEO4J_FALLBACK_DATABASE", None) or "").strip() or "neo4j"
 
    pool: list[str] = []
    seen: set[str] = set()
 
    def add_name(n: str | None) -> None:
        if not n or n in seen:
            return
        seen.add(n)
        pool.append(n)
 
    if explicit:
        add_name(explicit)
    for n in discovered:
        add_name(n)
    if fb:
        add_name(fb)
    if not pool and fb:
        add_name(fb)
 
    discovered_set = set(discovered)
    if not explicit and "neo4j" in discovered_set:
        names = ["neo4j"] + [n for n in pool if n != "neo4j"]
    else:
        names = list(pool)
 
    candidates: list[dict[str, Any]] = [{"database": n} for n in names]
    candidates.append({})
 
    if names:
        logger.info("Neo4j 세션 DB 시도 순서: %s → (database 생략·홈)", names)
    else:
        logger.info("Neo4j: 이름 후보 없음 — database 생략(홈)만 시도합니다.")
    return candidates
 
 
def run_query_with_db_fallback(driver: Any, work: Callable[[Any], T]) -> T:
    last_err: BaseException | None = None
    for skw in iter_session_kwarg_candidates(driver):
        try:
            with driver.session(**skw) as session:
                return work(session)
        except Exception as e:
            if neo4j_database_not_found(e):
                last_err = e
                logger.debug("Neo4j DB 후보 실패 %s: %s", skw or "(홈)", e)
                continue
            raise
    if last_err is not None:
        raise last_err
    raise RuntimeError("Neo4j 세션 후보가 없습니다.")
 
 
def run_write_with_db_fallback(driver: Any, work: Callable[[Any], None]) -> None:
    last_err: BaseException | None = None
    for skw in iter_session_kwarg_candidates(driver):
        try:
            with driver.session(**skw) as session:
                work(session)
                return
        except Exception as e:
            if neo4j_database_not_found(e):
                last_err = e
                logger.debug("Neo4j DB 후보 실패 %s: %s", skw or "(홈)", e)
                continue
            raise
    if last_err is not None:
        raise last_err
    raise RuntimeError("Neo4j 세션 후보가 없습니다.")
 
 
def _normalize_neo4j_uri(uri: str) -> str:
    """공백·따옴표 제거, 잘못 붙여넣은 https:// Aura 호스트 → Bolt 호환 스킴으로 보정."""
    u = str(uri).strip().strip('"').strip("'")
    if u.startswith("https://") and "databases.neo4j.io" in u:
        host = u.replace("https://", "", 1).split("/")[0].split("?")[0]
        host = host.split(":")[0]
        fixed = f"neo4j+s://{host}"
        logger.warning("NEO4J_URI가 https:// 로 되어 있어 드라이버용으로 %s 로 바꿉니다.", fixed)
        return fixed
    return u
 
 
def _apply_ssl_relaxed_uri(uri: str) -> str:
    """Neo4j 드라이버: +ssc 는 인증서 검증을 완화(자체 서명/일부 Windows SSL 이슈 대응)."""
    u = uri
    if u.startswith("bolt+s://"):
        return "bolt+ssc://" + u[len("bolt+s://"):]
    if u.startswith("neo4j+s://"):
        return "neo4j+ssc://" + u[len("neo4j+s://"):]
    return u
 
 
def _uri_has_embedded_tls(uri: str) -> bool:
    """bolt+s / +ssc / neo4j+s 등은 URI에 TLS가 포함됨. 이때 ssl_context 를 넘기면 드라이버가 거부함."""
    scheme = uri.split("://", 1)[0].lower()
    return scheme in ("bolt+s", "bolt+ssc", "neo4j+s", "neo4j+ssc")
 
 
def _driver_extra_kwargs(uri: str) -> dict:
    if _uri_has_embedded_tls(uri):
        return {}
    if not getattr(settings, "NEO4J_SSL_USE_CERTIFI", True):
        return {}
    try:
        import ssl
 
        import certifi
 
        return {"ssl_context": ssl.create_default_context(cafile=certifi.where())}
    except Exception as e:
        logger.debug("Neo4j ssl_context(certifi) 생략: %s", e)
        return {}
 
 
def _create_neo4j_driver() -> Any | None:
    uri = getattr(settings, "NEO4J_URI", None)
    if not uri:
        return None
    uri = _normalize_neo4j_uri(uri)
    if getattr(settings, "NEO4J_SSL_RELAXED", False):
        uri = _apply_ssl_relaxed_uri(uri)
        logger.info("NEO4J_SSL_RELAXED: URI를 완화 스킴으로 사용합니다.")
    try:
        from neo4j import GraphDatabase
    except ImportError as e:
        logger.error("neo4j package not installed: %s", e)
        return None
 
    auth = None
    user = getattr(settings, "NEO4J_USER", None)
    password = getattr(settings, "NEO4J_PASSWORD", None)
    if user is not None and password is not None:
        auth = (user, password)
    extra = _driver_extra_kwargs(uri)
    return GraphDatabase.driver(uri, auth=auth, **extra)
 
 
def get_neo4j_driver() -> Any:
    existing = getattr(_driver_tls, "driver", None)
    if existing is not None:
        return existing
    d = _create_neo4j_driver()
    _driver_tls.driver = d
    return d
 
 
def close_neo4j_driver() -> None:
    d = getattr(_driver_tls, "driver", None)
    if d is not None:
        try:
            d.close()
        except Exception as e:
            logger.warning("Neo4j driver close: %s", e)
        _driver_tls.driver = None