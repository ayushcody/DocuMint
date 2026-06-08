## 2026-06-08 - 64% Audit Regression Baseline

- Golden set PDFs: generated all 7 required root fixtures with `scripts/generate_golden_set.py`.
- Regression suite: `28 passed, 2 skipped` with `pytest tests/regression -q --regression`.
- Unit suite: `12 passed` with `pytest tests/unit -q`.
- Synthetic table baseline: token-level TEDS proxy is `1.0` for `sec_10k`, `invoice`,
  `bank_statement`, `academic_paper`, and `phone_photo`.
- Synthetic extraction baseline: expected manifest field presence is `100%` across all 7 PDFs.
- Confidence calibration baseline: regression contract asserts ECE `< 0.05` on the calibration
  sanity set.
- Verifier integration baseline: WeasyPrint rendering and SSIM differentiation tests pass.
- ColPali/Qdrant baseline: not fully established on this workstation. Docker is unavailable, so
  Qdrant-backed tests skipped; ColPali model initialization did not complete within the local
  verification window and must be rerun on a provisioned model/runtime host.
