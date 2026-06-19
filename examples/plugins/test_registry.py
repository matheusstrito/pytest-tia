from registry import dispatch


def test_greet():
    assert dispatch("greet", "ann") == "hello ann"


def test_shout():
    assert dispatch("shout", "ann") == "HELLO ANN"
