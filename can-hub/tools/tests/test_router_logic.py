def destinations(src: int, enable: list[int]) -> list[int]:
    assert len(enable) == 8 and enable[0] == 1
    if not enable[src]:
        return []
    if src == 0:
        return [i for i in range(1, 8) if enable[i]]
    return [0]


def test_fc_to_enabled_only():
    en = [1, 1, 0, 1, 0, 0, 0, 0]
    assert destinations(0, en) == [1, 3]


def test_branch_only_to_fc():
    en = [1, 1, 1, 1, 1, 1, 1, 1]
    assert destinations(2, en) == [0]


def test_disabled_src_drops():
    en = [1, 1, 0, 1, 0, 0, 0, 0]
    assert destinations(2, en) == []
