# Table Loss

Table reconstruction training should combine detection, token-to-cell assignment, span prediction, TEDS, and render MSE. The first implemented table-specific formula is multi-page stitch scoring in `workers/assembly.py`.
