"""Hybrid intent classification service for v1_0 workflow."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage

logger = logging.getLogger(__name__)

INTENT_LABELS = ("code_change", "code_review", "support")

_CODE_REVIEW_PATTERNS = [
    r"코드\s*리뷰", r"code\s*review", r"정적\s*분석", r"소나큐브", r"sonarqube",
    r"품질\s*게이트", r"quality\s*gate", r"취약점\s*점검", r"코드\s*품질",
]

_CODE_CHANGE_PATTERNS = [
    r"코드\s*수정", r"수정해\s*줘", r"리팩토링", r"리팩터링", r"버그\s*수정",
    r"fix\s+this", r"implement", r"구현해\s*줘", r"함수\s*고쳐", r"패치해",
]


def _collect_rule_signals(query: str) -> dict[str, list[str]]:
    review_hits = [p for p in _CODE_REVIEW_PATTERNS if re.search(p, query, re.IGNORECASE)]
    change_hits = [p for p in _CODE_CHANGE_PATTERNS if re.search(p, query, re.IGNORECASE)]
    return {
        "code_review": review_hits,
        "code_change": change_hits,
    }


def classify_intent_by_rules(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "intent": "support",
            "confidence": 0.3,
            "reason": "빈 질의는 일반 문의로 처리",
            "signals": [],
            "source": "rule",
            "ambiguous": False,
        }

    signals = _collect_rule_signals(q)
    review_hits = signals["code_review"]
    change_hits = signals["code_change"]

    if review_hits and not change_hits:
        return {
            "intent": "code_review",
            "confidence": 0.95,
            "reason": "코드리뷰/정적분석 관련 명시 키워드 매칭",
            "signals": review_hits,
            "source": "rule",
            "ambiguous": False,
        }
    if change_hits and not review_hits:
        return {
            "intent": "code_change",
            "confidence": 0.9,
            "reason": "코드 수정/구현 관련 명시 키워드 매칭",
            "signals": change_hits,
            "source": "rule",
            "ambiguous": False,
        }
    if review_hits and change_hits:
        return {
            "intent": "code_review",
            "confidence": 0.55,
            "reason": "코드리뷰와 코드수정 신호가 동시에 존재",
            "signals": review_hits + change_hits,
            "source": "rule",
            "ambiguous": True,
        }

    return {
        "intent": "support",
        "confidence": 0.5,
        "reason": "명시적 코드 작업 신호 없음",
        "signals": [],
        "source": "rule",
        "ambiguous": True,
    }


async def classify_intent_with_llm(query: str) -> dict[str, Any]:
    provider = get_provider(None)
    system_prompt = (
        "너는 사용자 요청을 intent로 분류하는 라우터다. "
        "반드시 JSON 하나만 반환한다. "
        "intent는 code_change/code_review/support 중 하나만 허용한다.\n"
        "code_change: 코드 수정/구현/리팩토링 요청\n"
        "code_review: 정적분석, 소나큐브, 품질 점검 요청\n"
        "support: 일반 문의/운영 응대/설명 요청\n"
        '반환 스키마: {"intent":"...","confidence":0~1,"reason":"...","signals":["..."]}'
    )
    resp = await provider.generate(
        [ChatMessage(role="user", content=f"질의: {query}")],
        system_prompt=system_prompt,
    )
    text = (resp.content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()
    parsed = json.loads(text)
    intent = parsed.get("intent", "support")
    if intent not in INTENT_LABELS:
        intent = "support"
    confidence = float(parsed.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))
    return {
        "intent": intent,
        "confidence": confidence,
        "reason": str(parsed.get("reason", "LLM 분류 결과")),
        "signals": parsed.get("signals", []) if isinstance(parsed.get("signals"), list) else [],
        "source": "llm",
        "ambiguous": False,
    }


async def classify_intent_hybrid(query: str) -> dict[str, Any]:
    rule_result = classify_intent_by_rules(query)
    if not rule_result.get("ambiguous"):
        return rule_result

    try:
        llm_result = await classify_intent_with_llm(query)
        llm_result["rule_reason"] = rule_result.get("reason", "")
        llm_result["rule_signals"] = rule_result.get("signals", [])
        return llm_result
    except Exception as exc:
        logger.warning("Intent LLM classifier failed, fallback to rule: %s", exc)
        fallback = dict(rule_result)
        fallback["source"] = "fallback_rule"
        fallback["ambiguous"] = False
        return fallback
