import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _divider() -> dict:
    return {"type": "divider"}


def build_blocks(data: dict) -> list:
    """MEDDIC 데이터를 Salesforce 붙여넣기 친화적인 텍스트 블록으로 변환."""
    title = data.get("meeting_title", "디스커버리 미팅")
    date = data.get("meeting_date") or "날짜 미상"
    completeness = data.get("meddic_completeness", 0)
    meddic = data.get("meddic", {})

    blocks = []

    # Header + 날짜/완성도
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"[디스커버리 미팅 회의록] {title}",
                "emoji": False,
            },
        }
    )
    blocks.append(
        _section(f"날짜: {date} | MEDDIC 완성도: {completeness}%")
    )

    blocks.append(_divider())

    # Metrics
    metrics = meddic.get("metrics", {})
    metrics_summary = metrics.get("summary") or "정보 없음"
    metrics_details = metrics.get("details") or []
    metrics_text = f"*Metrics*\n{metrics_summary}"
    if metrics_details:
        metrics_text += "\n" + "\n".join(f"- {d}" for d in metrics_details)
    blocks.append(_section(metrics_text))

    # Economic Buyer
    eb = meddic.get("economic_buyer", {})
    eb_confirmed = "Y" if eb.get("confirmed") else "N"
    eb_name = eb.get("name") or "미확인"
    eb_title = eb.get("title") or ""
    eb_person = f"{eb_name} / {eb_title}" if eb_title else eb_name
    blocks.append(_section(f"*Economic Buyer*\n확인 여부: {eb_confirmed} / {eb_person}"))

    # Decision Criteria
    dc = meddic.get("decision_criteria", {})
    dc_summary = dc.get("summary") or "정보 없음"
    dc_details = dc.get("details") or []
    dc_text = f"*Decision Criteria*\n{dc_summary}"
    if dc_details:
        dc_text += "\n" + "\n".join(f"- {d}" for d in dc_details)
    blocks.append(_section(dc_text))

    # Decision Process
    dp = meddic.get("decision_process", {})
    dp_summary = dp.get("summary") or "정보 없음"
    dp_timeline = dp.get("timeline")
    dp_text = f"*Decision Process*\n{dp_summary}"
    if dp_timeline:
        dp_text += f"\n타임라인: {dp_timeline}"
    blocks.append(_section(dp_text))

    # Identify Pain
    pain = meddic.get("identify_pain", {})
    pain_summary = pain.get("summary") or "정보 없음"
    pain_details = pain.get("details") or []
    pain_text = f"*Identify Pain*\n{pain_summary}"
    if pain_details:
        pain_text += "\n" + "\n".join(f"- {d}" for d in pain_details)
    blocks.append(_section(pain_text))

    # Champion
    champ = meddic.get("champion", {})
    strength = champ.get("strength", "unknown")
    champ_name = champ.get("name") or "미확인"
    champ_title = champ.get("title") or ""
    champ_person = f"{champ_name} / {champ_title}" if champ_title else champ_name
    champ_summary = champ.get("summary") or "정보 없음"
    blocks.append(_section(f"*Champion*\n강도: {strength} / {champ_person}\n{champ_summary}"))

    # Competition
    comp = meddic.get("competition", {})
    comp_mentioned = comp.get("mentioned", False)
    comp_summary = comp.get("summary") or ("경쟁사 언급 없음" if not comp_mentioned else "정보 없음")
    competitors = comp.get("competitors") or []
    comp_text = f"*Competition*\n{comp_summary}"
    if competitors:
        comp_text += "\n경쟁사: " + ", ".join(competitors)
    blocks.append(_section(comp_text))

    blocks.append(_divider())

    # Overall Assessment
    overall = data.get("overall_assessment") or "평가 없음"
    blocks.append(_section(f"*Overall Assessment*\n{overall}"))

    # Next Steps
    next_steps = data.get("next_steps") or []
    if next_steps:
        ns_lines = []
        for ns in next_steps:
            action = ns.get("action", "")
            owner = ns.get("owner") or "미정"
            due = ns.get("due_date")
            line = f"- {action} → {owner}"
            if due:
                line += f" / {due}"
            ns_lines.append(line)
        blocks.append(_section("*Next Steps*\n" + "\n".join(ns_lines)))

    return blocks


def build_summary_blocks(data: dict) -> list:
    """일반 회의록 요약 데이터를 텍스트 블록으로 변환."""
    title = data.get("meeting_title", "회의록")
    date = data.get("meeting_date") or "날짜 미상"

    blocks = []

    # Header + 날짜
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"[회의록] {title}",
                "emoji": False,
            },
        }
    )
    blocks.append(_section(f"날짜: {date}"))

    blocks.append(_divider())

    # Purpose
    purpose = data.get("purpose") or "정보 없음"
    blocks.append(_section(f"*회의 목적*\n{purpose}"))

    # Key Points
    key_points = data.get("key_points") or []
    if key_points:
        kp_lines = "\n".join(f"• {kp}" for kp in key_points)
        blocks.append(_section(f"*주요 내용*\n{kp_lines}"))

    # Next Steps
    next_steps = data.get("next_steps") or []
    if next_steps:
        ns_lines = []
        for ns in next_steps:
            action = ns.get("action", "")
            owner = ns.get("owner") or "미정"
            due = ns.get("due_date")
            line = f"• {action} → {owner}"
            if due:
                line += f" / {due}"
            ns_lines.append(line)
        blocks.append(_section("*Next Steps*\n" + "\n".join(ns_lines)))

    return blocks


def send_summary_to_slack(channel: str, data: dict, doc_title: str = "") -> None:
    """Slack 채널로 일반 회의록 요약을 전송한다.

    Args:
        channel: Slack 채널 (예: #ae-discovery)
        data: 요약 JSON 데이터
        doc_title: Google Docs 문서 제목
    """
    token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=token)

    blocks = build_summary_blocks(data)
    fallback_text = f"회의록 요약: {doc_title or data.get('meeting_title', '회의록')}"

    try:
        client.chat_postMessage(
            channel=channel,
            text=fallback_text,
            blocks=blocks,
        )
    except SlackApiError as e:
        raise RuntimeError(f"Slack 전송 실패: {e.response['error']}") from e


def send_meddic_to_slack(channel: str, data: dict, doc_title: str = "") -> None:
    """Slack 채널로 MEDDIC 분석 결과를 전송한다.

    Args:
        channel: Slack 채널 (예: #ae-discovery)
        data: MEDDIC JSON 데이터
        doc_title: Google Docs 문서 제목
    """
    token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=token)

    blocks = build_blocks(data)
    fallback_text = f"MEDDIC 분석 완료: {doc_title or data.get('meeting_title', '디스커버리콜')}"

    try:
        client.chat_postMessage(
            channel=channel,
            text=fallback_text,
            blocks=blocks,
        )
    except SlackApiError as e:
        raise RuntimeError(f"Slack 전송 실패: {e.response['error']}") from e
