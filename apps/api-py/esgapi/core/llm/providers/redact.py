"""공급사 오류 문구에 키(일부가 가려진 꼴 포함)가 섞여 와도 결과와 출력에 남지 않게 지운다."""

import re

# `sk-` 로 시작하는 꼴(OpenAI, Anthropic)과 `AIza` 로 시작하는 꼴(Google).
_SK = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_*.-]{4,}")
_AIZA = re.compile(r"(?<![A-Za-z0-9])AIza[A-Za-z0-9_*-]{8,}")


def redact_keys(text: str) -> str:
    return _AIZA.sub("AIza[가림]", _SK.sub("sk-[가림]", text))
