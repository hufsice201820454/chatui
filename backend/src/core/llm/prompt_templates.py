"""
Prompt template management (BE-LLM-03).
Templates are stored in the database (PromptTemplate model) and cached in memory.
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.models import PromptTemplate

logger = logging.getLogger("chatui.llm.templates")

# In-process cache: name → (version, system_prompt, few_shot_examples)
_cache: dict[str, PromptTemplate] = {}


async def get_template(name: str, db: AsyncSession) -> Optional[PromptTemplate]:
    if name in _cache:
        return _cache[name]
    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.name == name, PromptTemplate.is_active.is_(True))
        .order_by(PromptTemplate.version.desc())
    )
    tpl = result.scalar_one_or_none()
    if tpl:
        _cache[name] = tpl
    return tpl


async def upsert_template(
    name: str,
    system_prompt: Optional[str],
    few_shot_examples: Optional[list],
    db: AsyncSession,
) -> PromptTemplate:
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.name == name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.version += 1
        existing.system_prompt = system_prompt
        existing.few_shot_examples = few_shot_examples
        existing.is_active = True
        tpl = existing
    else:
        tpl = PromptTemplate(
            name=name,
            system_prompt=system_prompt,
            few_shot_examples=few_shot_examples or [],
        )
        db.add(tpl)

    await db.flush()
    _cache[name] = tpl
    logger.info("Upserted prompt template '%s' v%d", name, tpl.version)
    return tpl


def invalidate_cache(name: str | None = None) -> None:
    if name:
        _cache.pop(name, None)
    else:
        _cache.clear()
