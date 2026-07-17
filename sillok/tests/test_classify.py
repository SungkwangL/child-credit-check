from sillok_pipeline.classify import classify


def test_single_match():
    assert classify("영의정 아무개가 졸하다", "領議政 某 卒") == ["졸기"]


def test_hanja_and_korean():
    assert "재변" in classify("지진이 있었다", "地震")
    assert "붕어" in classify("상이 승하하다", "上薨")


def test_multiple_types():
    out = classify("반정으로 즉위하다", "反正 卽位")
    assert "반정" in out and "즉위" in out


def test_no_match():
    assert classify("경연을 열다", "經筵") == []
