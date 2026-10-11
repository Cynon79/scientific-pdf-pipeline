# Third-party integrations and rights

This private snapshot does not include a general open-source license. Project-code ownership, collaborator permissions and any later distribution license remain to be confirmed. Synthetic examples are authored for this snapshot; they are not copied from papers.

- **MinerU** is the upstream PDF parser integrated by the optional scripts. Its parser/model implementation and weights are not vendored; `requirements-parser.in` records the original dependency pins. This project must not be credited with developing MinerU or training its OCR/layout models.
- **PyMuPDF** provides native PDF geometry/text extraction and rendering. It is an external dependency, not copied source. Its licensing/redistribution requirements must be reviewed for the intended deployment before distribution.
- **fonttools** provides CFF/font outline parsing. It is an external dependency, not copied source.
- **SQLite FTS5** and the Python standard library provide local indexing, integrity checks and utilities.
- The optional original parser adapter also imports PyTorch, OpenCV, pypdf, Ultralytics and RapidTable through its separate environment. Those implementations/models are not included.

The workflow-specific code covers orchestration, coordinate-aware preservation, evidence links, review flags, cleaning and validation. Personal and collaborator contribution attribution is not established solely by this copied code. Credit AI-assisted development where applicable once roles are confirmed. No paper corpus or third-party article excerpts are bundled.
