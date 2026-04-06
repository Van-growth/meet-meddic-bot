import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import schedule
import time
from dotenv import load_dotenv

from google_docs_reader import get_google_clients, get_new_docs, read_doc_text
from meddic_extractor import extract_meddic, extract_summary
from slack_sender import send_meddic_to_slack, send_summary_to_slack

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DISCOVERY_KEYWORDS = ["디스커버리미팅", "디스커버리 미팅"]
PROCESSED_DOCS_FILE = Path("processed_docs.json")
MIN_TEXT_LENGTH = 200


def _load_processed() -> set:
    if PROCESSED_DOCS_FILE.exists():
        with open(PROCESSED_DOCS_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_processed(doc_ids: set) -> None:
    with open(PROCESSED_DOCS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(doc_ids), f, ensure_ascii=False, indent=2)


def is_discovery_doc(name: str) -> bool:
    """이중 필터: 키워드 포함 여부 확인."""
    name_lower = name.lower()
    return any(kw in name_lower or kw in name for kw in DISCOVERY_KEYWORDS)


def run_pipeline() -> None:
    """메인 파이프라인: 새 문서 감지 → MEDDIC 추출 → Slack 전송."""
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    slack_channel = os.environ.get("SLACK_CHANNEL", "#ae-discovery")

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )

    processed = _load_processed()

    try:
        drive, docs = get_google_clients()
    except Exception as e:
        logger.error("Google 클라이언트 초기화 실패: %s", e)
        return

    try:
        new_docs = get_new_docs(drive, folder_id, since)
    except Exception as e:
        logger.error("Drive 폴링 실패: %s", e)
        return

    if not new_docs:
        logger.info("새 문서 없음 (since=%s)", since)
        return

    for doc in new_docs:
        doc_id = doc["id"]
        doc_name = doc["name"]

        if doc_id in processed:
            logger.debug("이미 처리됨: %s", doc_name)
            continue

        logger.info("처리 시작: %s (%s)", doc_name, doc_id)

        try:
            text = read_doc_text(docs, doc_id)
        except Exception as e:
            logger.error("문서 읽기 실패 [%s]: %s", doc_name, e)
            continue

        if len(text.strip()) < MIN_TEXT_LENGTH:
            logger.warning("텍스트 너무 짧음 (%d자), 스킵: %s", len(text.strip()), doc_name)
            processed.add(doc_id)
            _save_processed(processed)
            continue

        if is_discovery_doc(doc_name):
            # 디스커버리콜 → MEDDIC 분석
            try:
                data = extract_meddic(text, meeting_title=doc_name)
            except Exception as e:
                logger.error("MEDDIC 추출 실패 [%s]: %s", doc_name, e)
                continue

            try:
                send_meddic_to_slack(slack_channel, data, doc_title=doc_name)
                logger.info("MEDDIC Slack 전송 완료: %s", doc_name)
            except Exception as e:
                logger.error("MEDDIC Slack 전송 실패 [%s]: %s", doc_name, e)
                continue
        else:
            # 일반 회의록 → 요약
            try:
                data = extract_summary(text, meeting_title=doc_name)
            except Exception as e:
                logger.error("요약 추출 실패 [%s]: %s", doc_name, e)
                continue

            try:
                send_summary_to_slack(slack_channel, data, doc_title=doc_name)
                logger.info("요약 Slack 전송 완료: %s", doc_name)
            except Exception as e:
                logger.error("요약 Slack 전송 실패 [%s]: %s", doc_name, e)
                continue

        processed.add(doc_id)
        _save_processed(processed)

    logger.info("파이프라인 완료")


def main() -> None:
    poll_interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

    logger.info("meet-meddic-bot 시작 (폴링 간격: %d초)", poll_interval)

    # 시작 시 즉시 1회 실행
    run_pipeline()

    schedule.every(poll_interval).seconds.do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
