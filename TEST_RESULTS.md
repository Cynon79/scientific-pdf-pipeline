# Snapshot verification

Verification date: 2026-10-11. All executions used the copied snapshot, no source edits, no model/provider calls, and no research corpus. Python 3.10.18, PyMuPDF 1.26.4, fonttools 4.64.0; SQLite FTS5 available.

## Observed results

- **54 tests passed; 0 failures, 0 errors, 0 skipped.** Twelve top-level synthetic test files plus six cleaner tests in one nested test file. Coverage includes caption boundaries/roles, figure-region preservation, continued assets, archive traversal/conflicts, content identity, invalid references, source crop reuse, conservative text repair, search-transcription separation and metadata-cleaning safety.
- **Synthetic pipeline passed:** one authored one-page PDF + mock layout; two body blocks, one figure, one equation, one caption, five search records.
- **Resume passed:** second run processed zero new documents after checking publication identity.
- **Integrity passed:** 19 document artifacts verified against receipts; source PDF/layout/library identity and processor signature checked. Output contained no PDF.
- **Derived cleaning and equation search passed.** No source package changed; result retained `scientific_accuracy=not_certified`/unreviewed status.

Exact test names and execution evidence: [TEST_RUN.txt](docs/TEST_RUN.txt), [SYNTHETIC_RUN.txt](docs/SYNTHETIC_RUN.txt). Absolute snapshot paths in saved evidence were replaced with `<snapshot>` and temporary directories with `<temporary>` for portability.

## Runtime isolation

Commands were launched with an explicit environment containing only PATH, offline flags and thread/bytecode settings; no inherited API credentials. Child Python used `-I -B`. A Python audit hook rejected socket connect/address lookup/bind events. Copied code and the existing source-local `analysis/native_deps` dependency installation were added to the child import path; third-party packages were not copied. This validates execution with those pinned dependency versions, not a fresh pip installation. The normal portable commands are in README.

## Not verified

No full MinerU parsing/model downloads, GPU/MPS run, real-paper OCR/chemical correctness, corpus-scale throughput, independent scientific benchmark or collaborator ownership review. Six real-corpus test files are excluded and listed in SOURCE_MANIFEST.json; omission is not a test pass. The archived local cleaner used in this snapshot was not compared with the external Codex skill currently referenced by the original script. Its unchanged byte hash and the six existing cleaner safety tests provide the bounded provenance/behavior evidence.
