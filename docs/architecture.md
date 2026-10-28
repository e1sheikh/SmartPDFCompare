# Architecture

`extraction` reads positioned words from PyMuPDF. `normalization` produces conservative comparison keys. `alignment` creates one-to-one page pairs. `diff` uses those same word streams for structured text records and annotation coordinates. `api` aggregates the result; `highlighting` consumes its private geometry, so summaries and marks cannot diverge.

`visual` is a separate rendered-page engine. It uses PyMuPDF pixmaps and standard-library byte processing—no OpenCV, NumPy, or GUI dependency—to compare index-paired pages on a padded common canvas and optionally write PNG artifacts. `viewer` is an optional lazy-Tk entry point which reuses `compare_pdfs` and its internal markup rather than implementing another text-diff algorithm. `cli` calls the public APIs.
