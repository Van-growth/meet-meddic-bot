import json
import re

import anthropic

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """당신은 B2B 영업 전문가입니다. 회의록 텍스트를 분석하여 MEDDIC 프레임워크에 따라 정보를 추출합니다.
반드시 JSON만 응답하세요. 마크다운 코드블록(```), 설명 텍스트, 기타 포맷 없이 순수 JSON만 출력하세요."""

USER_PROMPT_TEMPLATE = """다음 회의록을 분석하여 MEDDIC 프레임워크 정보를 추출해주세요.

회의록:
{transcript}

아래 JSON 구조로 정확히 응답하세요. 정보가 없는 필드는 null 또는 빈 배열로 채우세요:

{{
  "meeting_title": "회의 제목",
  "meeting_date": "YYYY-MM-DD 형식 날짜 또는 null",
  "meddic": {{
    "metrics": {{
      "summary": "핵심 지표 요약",
      "details": ["지표1", "지표2"]
    }},
    "economic_buyer": {{
      "summary": "경제적 의사결정권자 요약",
      "name": "이름 또는 null",
      "title": "직책 또는 null",
      "confirmed": false
    }},
    "decision_criteria": {{
      "summary": "의사결정 기준 요약",
      "details": ["기준1", "기준2"]
    }},
    "decision_process": {{
      "summary": "의사결정 프로세스 요약",
      "timeline": "타임라인 또는 null"
    }},
    "identify_pain": {{
      "summary": "핵심 Pain Point 요약",
      "details": ["pain1", "pain2"]
    }},
    "champion": {{
      "summary": "챔피언 요약",
      "name": "이름 또는 null",
      "title": "직책 또는 null",
      "strength": "strong 또는 moderate 또는 weak 또는 unknown"
    }},
    "competition": {{
      "mentioned": false,
      "competitors": ["경쟁사1"],
      "summary": "경쟁 상황 요약 또는 null"
    }}
  }},
  "next_steps": [
    {{"action": "액션 내용", "owner": "담당자", "due_date": "날짜 또는 null"}}
  ],
  "overall_assessment": "전반적인 딜 평가",
  "meddic_completeness": 75
}}"""


SUMMARY_SYSTEM_PROMPT = """당신은 회의록 요약 전문가입니다. 회의록 텍스트를 분석하여 핵심 내용을 구조화합니다.
반드시 JSON만 응답하세요. 마크다운 코드블록(```), 설명 텍스트, 기타 포맷 없이 순수 JSON만 출력하세요."""

SUMMARY_PROMPT_TEMPLATE = """다음 회의록을 분석하여 핵심 내용을 요약해주세요.

회의록:
{transcript}

아래 JSON 구조로 정확히 응답하세요. 정보가 없는 필드는 null 또는 빈 배열로 채우세요:

{{
  "meeting_title": "회의명",
  "meeting_date": "YYYY-MM-DD 형식 날짜 또는 null",
  "purpose": "회의 목적 한 줄 요약",
  "key_points": ["주요 내용 1", "주요 내용 2", "주요 내용 3"],
  "next_steps": [
    {{"action": "액션", "owner": "담당자 또는 null", "due_date": "기한 또는 null"}}
  ],
  "summary": "전체 회의 요약 2-3문장"
}}"""


def _parse_json_response(raw: str) -> dict:
    """Claude 응답에서 JSON 파싱 (코드블록 펜스 제거 포함)."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw.strip())


def extract_summary(transcript: str, meeting_title: str = "") -> dict:
    """회의록 텍스트에서 일반 요약 정보를 추출한다.

    Args:
        transcript: 회의록 전체 텍스트
        meeting_title: 문서 제목 (컨텍스트 보완용)

    Returns:
        dict: 요약 JSON 구조
    """
    client = anthropic.Anthropic()

    prompt_text = SUMMARY_PROMPT_TEMPLATE.format(transcript=transcript)
    if meeting_title:
        prompt_text = f"문서 제목: {meeting_title}\n\n" + prompt_text

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt_text}],
    )

    return _parse_json_response(response.content[0].text)


def extract_meddic(transcript: str, meeting_title: str = "") -> dict:
    """회의록 텍스트에서 MEDDIC 정보를 추출한다.

    Args:
        transcript: 회의록 전체 텍스트
        meeting_title: 문서 제목 (컨텍스트 보완용)

    Returns:
        dict: MEDDIC JSON 구조
    """
    client = anthropic.Anthropic()

    prompt_text = USER_PROMPT_TEMPLATE.format(transcript=transcript)
    if meeting_title:
        prompt_text = f"문서 제목: {meeting_title}\n\n" + prompt_text

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt_text}],
    )

    return _parse_json_response(response.content[0].text)
