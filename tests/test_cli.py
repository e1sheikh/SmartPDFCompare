import json

from smart_pdf_compare.cli import main


def test_cli_writes_json_and_exit_status(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["old"])
    new = pdf_factory("new.pdf", ["new"])
    output = tmp_path / "result.json"
    assert main([str(old), str(new), "--json", str(output)]) == 1
    assert json.loads(output.read_text())["is_identical"] is False
