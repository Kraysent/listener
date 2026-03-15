import pytest


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (2, 3, 5),
        (0, 5, 5),
        (7, 0, 7),
        (-1, -2, -3),
    ],
)
def test_add(a: int, b: int, expected: int) -> None:
    assert a + b == expected
