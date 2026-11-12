"""실행의 출력 파일 바이트를 저장소에서 읽는다(RF1 — 고객사 runs_file_get 과 운영 관리자 user_run_log_file_get 이 같이
쓴다). DB 를 읽지도 쓰지도 않는다 — 저장소만 읽는다, 감사는 부르는 쪽이 한다.

    output_bytes(file)   그 파일 행의 바이트. 객체가 없거나 상한을 넘으면 None(부르는 쪽이 자기 404)

★ 저장소가 없음·거절·닿지 못함은 503 셋(storage_unconfigured·storage_denied·storage_unavailable)의 ApplicationError 로
  던진다 — 두 경로의 code·글이 같아야 해서 여기 한 벌이다.
★ 저장소(documents.default_storage·max_upload_bytes)는 **부를 때마다 모듈 속성으로** 읽는다(테스트가 바꿔 끼운다).
  상한은 올림 상한(max_upload_bytes — 어림)과 같다.
"""

from esgapi.core.exceptions import ApplicationError
from esgapi.core.resources.ports.storage import ObjectBytes, StorageDenied, StorageUnavailable
from esgapi.core.service.services import documents
from esgapi.runs.service.selectors import runs as run_selectors


def output_bytes(file: run_selectors.RunFile) -> bytes | None:
    """그 파일의 바이트. 행은 있는데 객체가 없거나 상한을 넘으면 None — 내줄 바이트가 없다."""
    storage = documents.default_storage()
    if storage is None:
        raise ApplicationError("unavailable", "storage_unconfigured", "이 서버에 원본 파일 저장소가 준비되어 있지 않다")
    got = storage.get(file.storage_key, max_bytes=documents.max_upload_bytes())
    if isinstance(got, StorageDenied):
        raise ApplicationError("unavailable", "storage_denied", "저장소가 요청을 거절했다")
    if isinstance(got, StorageUnavailable):
        raise ApplicationError("unavailable", "storage_unavailable", "저장소에 닿지 못했다. 잠시 뒤 다시 시도해 달라")
    if not isinstance(got, ObjectBytes):
        return None
    return got.data
