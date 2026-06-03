from ddigraph.utils.chunking import chunked, window


def test_chunked_sizes() -> None:
    data = list(range(7))
    chunks = window(data, 3)
    assert chunks == [[0, 1, 2], [3, 4, 5], [6]]


def test_chunked_requires_positive_size() -> None:
    data = [1, 2, 3]
    try:
        list(chunked(data, 0))
    except ValueError:
        return
    raise AssertionError("chunked should raise when size <= 0")
