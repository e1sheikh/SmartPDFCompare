import json

from smart_pdf_compare.cli import main


def test_cli_writes_json_and_exit_status(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["old"])
    new = pdf_factory("new.pdf", ["new"])
    output = tmp_path / "result.json"
    assert main([str(old), str(new), "--json", str(output)]) == 1
    assert json.loads(output.read_text())["is_identical"] is False


def test_cli_can_run_visual_only_and_write_artifacts(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["old"])
    new = pdf_factory("new.pdf", ["new"])
    output = tmp_path / "visual.json"
    artifacts = tmp_path / "images"
    assert main([
        str(old), str(new), "--visual-only", "--visual-mode", "diff_image",
        "--visual-output-dir", str(artifacts), "--json", str(output),
    ]) == 1
    payload = json.loads(output.read_text())
    assert payload["pages"][0]["diff_image_path"]
