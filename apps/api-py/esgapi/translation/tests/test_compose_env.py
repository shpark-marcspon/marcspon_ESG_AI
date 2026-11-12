"""T3(MARC-ISSUE-331 의 2): compose.yaml 의 api-py 환경(앵커 api-py-env — worker-py 는 `<<:` 로 같은 것)이 영문번역 한
실행의 금액 상한 TRANSLATION_RUN_MAX_USD 를 빈 기본값으로 싣는다(core test_env_llm_run_mode.py 의 꼴). 빈 값은
config/env.py 가 기본 5.0 으로 읽는다."""

from pathlib import Path

KEY = "TRANSLATION_RUN_MAX_USD"


def _anchored_env(compose: str) -> str:
    """앵커 `&api-py-env` 의 줄부터 다음 서비스 머리(들여쓰기 두 칸) 앞까지."""
    start = compose.index("environment: &api-py-env")
    rest = compose[start:].split("\n")[1:]
    block: list[str] = []
    for line in rest:
        if line.startswith("  ") and not line.startswith("   "):  # 다음 서비스
            break
        block.append(line)
    return "\n".join(block)


def test_compose_carries_the_translation_cap_empty_in_the_api_py_anchor() -> None:
    root = Path(__file__).resolve().parents[5]
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    assert f"      {KEY}: ${{{KEY}:-}}\n" in _anchored_env(compose) + "\n"
    assert "<<: *api-py-env" in compose  # worker-py 가 api-py 의 환경을 그대로 받는다
