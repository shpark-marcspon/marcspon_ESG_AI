"""§3-1-5 지문의 이쪽 몫(BASE 와의 sha 대조는 scripts/section4-TR2.sh 가 BASE 트리로 한다): 지문에서 빼는 열쇠
`remaining_korean` 의 값 — 번역된 조각은 빈 것, 한국어 잔존으로 실패한 조각만 남은 줄."""

from typing import cast

from esgapi.translation.engines.colab_158.gates import collect_untranslated_korean_lines
from esgapi.translation.tests.engines.colab_158.run_digest import ADDED, CASES, digest
from esgapi.translation.tests.engines.colab_158.support import run_flow


def test_the_dropped_key_is_empty_except_on_the_korean_failure() -> None:
    for case in CASES:
        inputs, replies = CASES[case]
        for variant in run_flow(inputs, replies).run.variants:
            for fragment in variant.fragments:
                if case == "korean_left_w7" and fragment.page_num == 2:
                    assert fragment.status == "error"
                    assert fragment.remaining_korean == tuple(collect_untranslated_korean_lines("[BLOCK 1]\nleft 국문"))
                    assert fragment.remaining_korean != ()
                else:
                    assert (fragment.status, fragment.remaining_korean) == ("translated", ())


def test_the_digest_names_the_added_key_once_per_fragment_path() -> None:
    keys = cast("list[str]", digest()["keys"])
    assert [k for k in keys if k.endswith(f".{ADDED}")] == [f"run.variants[].fragments[].{ADDED}"]
