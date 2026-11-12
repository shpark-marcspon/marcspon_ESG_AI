"""zip 을 `zipfile.ZipFile` 로 열기 전의 가운데 목록 검사(밴드 TRS2, MARC-ISSUE-385). page_tags 와 docx_reader 가
같이 부른다.

`zipfile.ZipFile` 은 여는 자리에서 가운데 목록 전체를 ZipInfo 로 푼다 — 1바이트 이름 항목 100만 개(47MB)면 그 뒤에
항목 수를 보아도 이미 늦다(worker 메모리 +350MB). 그래서 끝의 EOCD 만 보고 가운데 목록 크기를 먼저 거른다.

    central_directory_refusal(data) -> "too_many_entries" | "unreadable" | None(열어도 됨)
"""

import struct
from typing import Final, Literal

MAX_CENTRAL_DIRECTORY: Final = 1024 * 1024
"""zip 가운데 목록 바이트 상한(항목 MAX_ENTRIES 개의 이름이 길어도 넉넉 — 정상 docx 는 수 KB)."""
_EOCD: Final = b"PK\x05\x06"
_EOCD_SIZE: Final = 22
_ZIP64_LOCATOR: Final = b"PK\x06\x07"


def central_directory_refusal(data: bytes) -> Literal["too_many_entries", "unreadable"] | None:
    """zipfile 이 찾을 EOCD(zipfile._EndRecData 꼴 — 주석 없는 끝 22바이트, 아니면 끝 64KiB+22 에서 마지막 것)의
    가운데 목록이 MAX_CENTRAL_DIRECTORY 를 넘거나 zip64 면 `too_many_entries`. EOCD 가 없으면 `unreadable`."""
    at = len(data) - _EOCD_SIZE
    if not (at >= 0 and data[at : at + 4] == _EOCD and data[-2:] == b"\x00\x00"):
        at = data.rfind(_EOCD, max(0, len(data) - _EOCD_SIZE - 0xFFFF))
        if at < 0 or len(data) - at < _EOCD_SIZE:
            return "unreadable"
    _, disk, start_disk, disk_entries, entries, size, offset, _ = struct.unpack("<4s4H2LH", data[at : at + _EOCD_SIZE])
    zip64 = 0xFFFF in (disk, start_disk, disk_entries, entries) or 0xFFFFFFFF in (size, offset)
    if zip64 or (at >= 20 and data[at - 20 : at - 16] == _ZIP64_LOCATOR) or size > MAX_CENTRAL_DIRECTORY:
        return "too_many_entries"
    return None
