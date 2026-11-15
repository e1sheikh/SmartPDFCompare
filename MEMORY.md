# Smart-PDF-Compare Memory

## Project Context
- Senior Python engineer with PDF-internals expertise
- Library for PDF comparison and highlighting
- Working branch: fixes/review-fixes-unverified
- Tasks: fix false positives/negatives, improve accuracy, implement phases 0-8

## Key Issues Found
- False positives on encoding differences (soft hyphens, bullets, degree symbols, Symbol font PUA)
- False negatives on non-text changes (logos, bold headings)
- Highlighting overshoots word boundaries
- Visual comparison separate from text

## Next Steps
Phase 0: Diagnostics and hygiene
