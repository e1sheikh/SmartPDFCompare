# Contributing

Create a virtual environment, install `python -m pip install -e ".[dev]"`, and run `python -m pytest` before opening a pull request. Tests create their own PDFs with PyMuPDF and must not depend on network files. Keep the public API typed and documented. Run `python -m build` and `python -m twine check dist/*` before a release.
