from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


def get_google_clients():
    """service_account.json으로 Drive/Docs 클라이언트 반환."""
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json", scopes=SCOPES
    )
    drive = build("drive", "v3", credentials=creds)
    docs = build("docs", "v1", credentials=creds)
    return drive, docs


def get_new_docs(drive, folder_id, since_timestamp):
    """폴더 내 since_timestamp 이후 생성된 디스커버리콜 Docs 반환.

    Args:
        drive: Google Drive 클라이언트
        folder_id: 폴더 ID
        since_timestamp: ISO 8601 형식 타임스탬프 (UTC)

    Returns:
        list of dict with id, name, createdTime
    """
    query = (
        f"'{folder_id}' in parents"
        " and mimeType='application/vnd.google-apps.document'"
        " and trashed=false"
        f" and createdTime > '{since_timestamp}'"
    )

    results = (
        drive.files()
        .list(
            q=query,
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc",
        )
        .execute()
    )

    return results.get("files", [])


def read_doc_text(docs, doc_id):
    """Docs 전체 텍스트 추출.

    Args:
        docs: Google Docs 클라이언트
        doc_id: 문서 ID

    Returns:
        str: 문서 전체 텍스트
    """
    document = docs.documents().get(documentId=doc_id).execute()
    body = document.get("body", {})
    content = body.get("content", [])

    texts = []
    for element in content:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for part in paragraph.get("elements", []):
            text_run = part.get("textRun")
            if text_run:
                texts.append(text_run.get("content", ""))

    return "".join(texts)
