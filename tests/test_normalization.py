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


def test_typographic_quotes_can_be_normalized_or_preserved():
    assert normalize_token("“quoted”") == '"quoted"'
    assert normalize_token("“quoted”", NormalizationOptions(normalize_quotes=False)) == "“quoted”"

def test_new_symbol_normalization():
    from smart_pdf_compare.normalization import normalize_token
    assert normalize_token("RϑJC") == normalize_token("RθJC")
    assert normalize_token("25℃") == normalize_token("25°C")
    assert normalize_token("1.6°") == normalize_token("1.6º")
