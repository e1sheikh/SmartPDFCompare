from smart_pdf_compare import NormalizationOptions
from smart_pdf_compare.normalization import normalize_token


def test_case_ligature_dash_and_nbsp_normalize():
    assert normalize_token("OFFICE") == normalize_token("o\ufb03ce")
    assert normalize_token("x\u2013y") == "x-y"
    assert normalize_token("\u00a0Hello\u00a0") == "hello"


def test_punctuation_policy_preserves_numbers_and_contractions():
    assert normalize_token("-1.5") == "-1.5"
    assert normalize_token("isn't") == "isn't"
    assert normalize_token("Hello!") == "hello!"
    assert normalize_token("Hello!", NormalizationOptions(ignore_punctuation=True)) == "hello"
