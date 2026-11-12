"""꼴 검사(`check`)가 내는 문제의 자리와 문구. 순수 층.

shape 를 쓰는 다른 시험(test_document.py·test_places.py)은 정본 꼴이 맞는지만 본다. 여기서는 틀린 값마다
`ShapeProblem` 전체(where·problem)를 == 로 견준다.
"""

from esgapi.reconcile.calc.shape import Arr, Field, Int, Obj, ShapeProblem, Str, check


def test_too_short_a_list_names_where_it_is() -> None:
    shape = Arr(Str(), min_length=2)
    assert check(["가"], shape) == ShapeProblem("(맨 위)", "길이가 2 이상이어야 한다(받은 것 1)")
    assert check(["가", "나"], shape) is None
    under = Obj({"blocks": Field(shape)})
    assert check({"blocks": []}, under) == ShapeProblem("blocks", "길이가 2 이상이어야 한다(받은 것 0)")
    deeper = Obj({"pages": Field(Arr(under))})
    assert check({"pages": [{"blocks": ["가", "나"]}, {"blocks": ["가"]}]}, deeper) == ShapeProblem(
        "pages[1].blocks", "길이가 2 이상이어야 한다(받은 것 1)"
    )


def test_a_missing_optional_field_does_not_stop_the_check_of_the_next_fields() -> None:
    shape = Obj({"note": Field(Str(), required=False), "page": Field(Int()), "title": Field(Str())})
    assert check({"page": "3", "title": "가"}, shape) == ShapeProblem("page", "정수여야 한다")
    assert check({"page": 3}, shape) == ShapeProblem("title", "칸이 없다")
    assert check({"page": 3, "title": "가"}, shape) is None
