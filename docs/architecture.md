# Architecture

`extraction` reads positioned words from PyMuPDF. `normalization` produces conservative comparison keys. `alignment` creates one-to-one page pairs. `diff` uses those same word streams for structured text records and annotation coordinates. `api` aggregates the result; `highlighting` consumes its private geometry, so summaries and marks cannot diverge. `cli` calls only the public API.
