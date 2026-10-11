# Source version and export record

Export date: 2026-10-11. Source directory: local project checkout (personal filesystem path omitted).

The selected `portable/build_native_assets.py` declares `native-assets-v0.11-boundary-annotations`. The snapshot uses the current source files directly; it does not use older delivery ZIPs. No Git revision identity is asserted and no source Git history was exported.

[docs/SOURCE_MANIFEST.json](docs/SOURCE_MANIFEST.json) lists 47 source-selected files with source-relative path, destination-relative path, original SHA-256, snapshot SHA-256 and explicit packaging changes. Source files were not modified.

Minimal copy-only adaptations:

1. Removed seven development-specific dependency-path/import-location usages across the documented changed files (six native dependency injections, one cleaner path rebinding; exact per-file changes are authoritative in the manifest).
2. `clean_preserved_md.py` now imports the adjacent archived `legacy_clean_md_batch.py`, copied byte-for-byte from `maintenance/20260911_merge_clean/`. Its SHA-256 is `9c9adca52936cb3d8accaacb8f9fd993915c79d2d0c02bb58d49e1468450c985`. The external skill file was not read and equality to its present contents is not claimed.
3. Replaced the postprocessor's deployment-specific remote PDF locator with null; the snapshot has no remote research library.
4. Copied the lightweight dependency pins into `requirements.txt` and the optional old parser pins into `requirements-parser.in`.

New material is limited to documentation, ignores, an authored synthetic-input generator, its verification records and the project-code license. No extraction/model algorithm was developed as part of packaging. The synthetic generator creates its own illustrative PDF and mock layout locally; these are not outputs of MinerU inference.

Excluded: PDFs and parsed-paper Markdown/JSON, `sample_bundle`, corpus-dependent tests, reports/analysis datasets, production/runtime collections, machine configs, .venv, dependency directories, models, caches, archives, old delivery trees and remote transfer credentials. On 2026-10-11, the project owner confirmed sole development of the workflow code with AI assistance and authorized GNU AGPLv3 for the project-owned code. [README.md](README.md#license) records the `AGPL-3.0-only` scope; third-party code, models and publications retain their separate terms.

The full, unmodified [LICENSE](LICENSE) text was copied from the [SPDX license list's AGPL-3.0-only text](https://github.com/spdx/license-list-data/blob/31ba1a50e5397e00a304dbadc76531740e89ee48/text/AGPL-3.0-only.txt). Licensing documentation changes do not change the exported source-file hashes or the recorded verification results.
