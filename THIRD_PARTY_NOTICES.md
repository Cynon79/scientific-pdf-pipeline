# Third-party integrations and rights

The project-owned workflow code was developed by Cynon79 with AI assistance and is licensed under GNU AGPL version 3 only (`AGPL-3.0-only`); see [README.md](README.md#license) for scope and [LICENSE](LICENSE) for the full terms. This grant does not relicense third-party dependencies, model weights or source publications. Synthetic examples are authored for this snapshot; they are not copied from papers.

- **MinerU** is the upstream PDF parser integrated by the optional scripts. The pinned [MinerU 2.0.4 release](https://pypi.org/project/mineru/2.0.4/) lists AGPL-3.0 in its package metadata. This version-specific notice does not assert the license of later releases. Its parser/model implementation and weights are not vendored; `requirements-parser.in` records the original dependency pins. This project must not be credited with developing MinerU or training its OCR/layout models.
- **PyMuPDF 1.26.4** provides native PDF geometry/text extraction and rendering. Its [release metadata](https://pypi.org/project/PyMuPDF/1.26.4/) identifies dual licensing under GNU AGPLv3 or an Artifex commercial license. It is an external dependency, not copied source; the applicable upstream terms still govern its use and redistribution.
- **fonttools** provides CFF/font outline parsing. It is an external dependency, not copied source.
- **SQLite FTS5** and the Python standard library provide local indexing, integrity checks and utilities.
- The optional original parser adapter also imports PyTorch, OpenCV, pypdf, Ultralytics and RapidTable through its separate environment. Those implementations/models are not included.

The workflow-specific code covers orchestration, coordinate-aware preservation, evidence links, review flags, cleaning and validation. No paper corpus or third-party article excerpts are bundled.

Dependencies and separately provisioned model weights must be used under their own applicable licenses. This notice is not a complete dependency/model license audit; review the actual versions and any distribution or hosted-service obligations for the intended deployment. Source-paper licensing continues to govern any later redistribution of papers or their content.
