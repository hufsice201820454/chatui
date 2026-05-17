"""
Product Code 이미지 파서 (MM / Hybrid 타입).
vision_client를 사용하여 내부망/외부망 API와 연동.
"""
import json
import logging
from typing import Optional

from src.core.llm import vision_client

logger = logging.getLogger("chatui.utils.product_code_parsers")

OUTPUT_COLUMNS = [
    "PLAN_PROD_ID",
    "MASK_REV_CD",
    "PROD_SITE_TRANSFER_CD",
    "PROD_SPECIAL_HANDLE_CD",
    "QUAL_INFO_CD",
    "FRONT_MASK_CD",
    "TEST_COND_CD",
    "SUBST_VENDOR_CD",
    "MCP_INFO_VAL",
    "STACK_SNO_INPUT_YN",
    "TGT_FAC_VAL",
]

MM_RULES = """
[MM 타입 Product Code 파싱 규칙]

1. 행 생성 기준
   - WLPKG Product Code 수 × PKG_DDA 생산속성 정보 수 = 총 행 수
   - WLPKG Product Code는 X값(arg)에 따라 구분: X4, X8 등 숫자는 이미지에서 org 컬럼 기준으로 결정
   - PKG_DDA 생산속성 정보의 각 항목(1., 2., ...)은 서로 다른 행으로 분리 (같은 행에 혼합 금지)

2. PLAN_PROD_ID
   - WLPKG 그룹의 Product Code 값 사용

3. MASK_REV_CD
   - PKG_DDA 생산속성 정보에서 "Mask REV:" 뒤의 값 추출
   - 해당 항목이 없는 행은 공백

4. PROD_SITE_TRANSFER_CD
   - WLPKG 생산속성 정보에서 "Product Site Transfer()" 괄호 안의 값 추출
   - 모든 행에 공통 적용

5. PROD_SPECIAL_HANDLE_CD
   - PKG_DDA 생산속성 정보에서 "Product Special Handling =" 뒤의 값 추출
   - 해당 항목이 없는 행은 공백

6. 나머지 컬럼 (QUAL_INFO_CD, FRONT_MASK_CD, TEST_COND_CD, SUBST_VENDOR_CD,
               MCP_INFO_VAL, STACK_SNO_INPUT_YN, TGT_FAC_VAL)
   - 이미지에서 해당 정보가 확인되면 추출, 없으면 공백("")

7. 값이 명확하지 않으면 반드시 공백("") 처리 — 추측 금지
"""

MM_FEW_SHOT = [
    {
        "description": "WLPKG 2개(X4, X8) × PKG_DDA 속성 2개(MASK_REV_CD, PROD_SPECIAL_HANDLE_CD) = 4행",
        "output": [
            {
                "PLAN_PROD_ID": "H5CG54-AAA02",
                "MASK_REV_CD": "BX(AA)",
                "PROD_SITE_TRANSFER_CD": "NCPB",
                "PROD_SPECIAL_HANDLE_CD": "",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "",
                "MCP_INFO_VAL": "",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "H5CG54-AAA02",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "NCPB",
                "PROD_SPECIAL_HANDLE_CD": "S1",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "",
                "MCP_INFO_VAL": "",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "H5CG58-AAA02",
                "MASK_REV_CD": "BX(AA)",
                "PROD_SITE_TRANSFER_CD": "NCPB",
                "PROD_SPECIAL_HANDLE_CD": "",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "",
                "MCP_INFO_VAL": "",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "H5CG58-AAA02",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "NCPB",
                "PROD_SPECIAL_HANDLE_CD": "S1",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "",
                "MCP_INFO_VAL": "",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
        ],
    }
]

HYBRID_RULES = """
[Hybrid 타입 Product Code 파싱 규칙]

1. 행 생성 기준
   - (Special 수 + 1) × Sub Vendor 수 = 총 행 수
   - Special: Center 속성, Edge 속성 각각 1개씩 (최대 2개)
   - Sub Vendor: MCP 속성 정보 내 "Sub Vendor:" 항목 수
   - 예) Special 2개 + 1 = 3, Sub Vendor 2개 → 3 × 2 = 6행

2. PLAN_PROD_ID
   - Device PKG 컬럼 값 사용

3. PROD_SPECIAL_HANDLE_CD
   - 행 묶음 순서: 특수속성 없음("") → Center 속성값 → Edge 속성값
   - 각 묶음 내에서 Sub Vendor 수만큼 행 반복
   - Center 속성 또는 Edge 속성이 없는 경우 해당 묶음 생략, 값은 ""

4. SUBST_VENDOR_CD
   - MCP 속성 정보에서 "Sub Vendor:" 뒤의 값 추출
   - 각 Special 묶음 안에서 Sub Vendor 순서대로 반복

5. MCP_INFO_VAL
   - SDP 컬럼 값을 모든 행에 공통 적용
   - SDP가 여러 개인 경우 콤마(,)로 연결

6. 나머지 컬럼 (MASK_REV_CD, PROD_SITE_TRANSFER_CD, QUAL_INFO_CD,
               FRONT_MASK_CD, TEST_COND_CD, STACK_SNO_INPUT_YN, TGT_FAC_VAL)
   - 이미지에서 해당 정보가 확인되면 추출, 없으면 공백("")

7. 값이 명확하지 않으면 반드시 공백("") 처리 — 추측 금지
"""

HYBRID_FEW_SHOT = [
    {
        "description": (
            "Device PKG: HBM3E_12H_24GB, "
            "Center 속성: CD, Edge 속성: EG, "
            "Sub Vendor 2개: LG SUB(L) / 삼텍 sub(s), "
            "SDP: DRAM(SP 24Gb_LPD5) "
            "→ (2+1) × 2 = 6행"
        ),
        "output": [
            {
                "PLAN_PROD_ID": "HBM3E_12H_24GB",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "",
                "PROD_SPECIAL_HANDLE_CD": "",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "LG SUB(L)",
                "MCP_INFO_VAL": "DRAM(SP 24Gb_LPD5)",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "HBM3E_12H_24GB",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "",
                "PROD_SPECIAL_HANDLE_CD": "",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "삼텍 sub(s)",
                "MCP_INFO_VAL": "DRAM(SP 24Gb_LPD5)",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "HBM3E_12H_24GB",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "",
                "PROD_SPECIAL_HANDLE_CD": "CD",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "LG SUB(L)",
                "MCP_INFO_VAL": "DRAM(SP 24Gb_LPD5)",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "HBM3E_12H_24GB",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "",
                "PROD_SPECIAL_HANDLE_CD": "CD",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "삼텍 sub(s)",
                "MCP_INFO_VAL": "DRAM(SP 24Gb_LPD5)",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "HBM3E_12H_24GB",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "",
                "PROD_SPECIAL_HANDLE_CD": "EG",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "LG SUB(L)",
                "MCP_INFO_VAL": "DRAM(SP 24Gb_LPD5)",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
            {
                "PLAN_PROD_ID": "HBM3E_12H_24GB",
                "MASK_REV_CD": "",
                "PROD_SITE_TRANSFER_CD": "",
                "PROD_SPECIAL_HANDLE_CD": "EG",
                "QUAL_INFO_CD": "",
                "FRONT_MASK_CD": "",
                "TEST_COND_CD": "",
                "SUBST_VENDOR_CD": "삼텍 sub(s)",
                "MCP_INFO_VAL": "DRAM(SP 24Gb_LPD5)",
                "STACK_SNO_INPUT_YN": "",
                "TGT_FAC_VAL": "",
            },
        ],
    }
]


def _build_mm_system_prompt() -> str:
    few_shot_str = json.dumps(MM_FEW_SHOT, ensure_ascii=False, indent=2)
    return f"""당신은 반도체 MES Product Code 이미지를 분석하여 구조화된 데이터를 추출하는 전문가입니다.
입력 타입은 MM입니다.

{MM_RULES}

[출력 컬럼]
{OUTPUT_COLUMNS}

[Few-shot 예시]
{few_shot_str}

[출력 형식 규칙]
- 반드시 JSON 배열만 반환 (```json 마크다운 감싸기 금지)
- 각 원소는 11개 컬럼을 모두 포함
- 값이 없으면 빈 문자열("") 사용, null 금지
- 추측 금지: 이미지에서 명확히 읽히는 값만 채울 것
"""


def _build_hybrid_system_prompt() -> str:
    few_shot_str = json.dumps(HYBRID_FEW_SHOT, ensure_ascii=False, indent=2)
    return f"""당신은 반도체 MES Product Code 이미지를 분석하여 구조화된 데이터를 추출하는 전문가입니다.
입력 타입은 Hybrid입니다.

{HYBRID_RULES}

[출력 컬럼]
{OUTPUT_COLUMNS}

[Few-shot 예시]
{few_shot_str}

[출력 형식 규칙]
- 반드시 JSON 배열만 반환 (```json 마크다운 감싸기 금지)
- 각 원소는 11개 컬럼을 모두 포함
- 값이 없으면 빈 문자열("") 사용, null 금지
- 추측 금지: 이미지에서 명확히 읽히는 값만 채울 것
"""


def _rows_to_markdown(rows: list[dict]) -> str:
    """파싱된 행 리스트를 마크다운 테이블로 변환."""
    if not rows:
        return "파싱 결과가 없습니다."

    header = " | ".join(OUTPUT_COLUMNS)
    separator = " | ".join(["---"] * len(OUTPUT_COLUMNS))
    data_rows = []
    for row in rows:
        data_rows.append(" | ".join(str(row.get(col, "")) for col in OUTPUT_COLUMNS))

    return f"| {header} |\n| {separator} |\n" + "\n".join(f"| {r} |" for r in data_rows)


async def parse_product_code_image(
    image_b64: str,
    mime: str,
    product_code_type: str,
) -> str:
    """
    MM 또는 Hybrid 타입 Product Code 이미지를 파싱하여 마크다운 테이블로 반환.

    Args:
        image_b64: base64 인코딩된 이미지
        mime: 이미지 MIME 타입 (e.g. "image/png")
        product_code_type: "mm" 또는 "hybrid"

    Returns:
        str: 파싱 결과 마크다운 테이블 + 행 수 요약
    """
    ptype = product_code_type.lower().strip()
    if ptype == "mm":
        system_prompt = _build_mm_system_prompt()
        user_text = "위 이미지는 MM 타입 Product Code입니다. 파싱 규칙에 따라 행을 생성하고 JSON 배열로 반환하세요."
        type_label = "MM"
    elif ptype == "hybrid":
        system_prompt = _build_hybrid_system_prompt()
        user_text = "위 이미지는 Hybrid 타입 Product Code입니다. 파싱 규칙에 따라 행을 생성하고 JSON 배열로 반환하세요."
        type_label = "Hybrid"
    else:
        raise ValueError(f"지원하지 않는 product_code_type: {product_code_type!r}. 'mm' 또는 'hybrid'를 사용하세요.")

    raw = await vision_client.analyze_image(
        image_b64=image_b64,
        mime=mime,
        text_prompt=user_text,
        system_prompt=system_prompt,
    )

    raw = raw.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        rows: list[dict] = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Product code JSON 파싱 실패: %s\nraw=%s", e, raw[:500])
        return f"[{type_label} 타입 파싱 오류] Vision 모델 응답을 JSON으로 변환하지 못했습니다.\n\n원본 응답:\n{raw}"

    for row in rows:
        for col in OUTPUT_COLUMNS:
            row.setdefault(col, "")

    md_table = _rows_to_markdown(rows)
    return f"**{type_label} 타입 Product Code 파싱 결과** (총 {len(rows)}행)\n\n{md_table}"
