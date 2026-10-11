# Scientific PDF Pipeline

Private code snapshot of a source-preserving scientific-document workflow. MinerU supplies layout; postprocessing reconstructs native PDF text, preserves figure/table/equation regions, associates captions, and builds searchable outputs with source coordinates and explicit review states.

Start with [the architecture guide for Kumar](docs/ARCHITECTURE.md). The copied postprocessor identifies itself as `native-assets-v0.11-boundary-annotations`. This is a workflow around upstream tools, not a newly trained OCR model.

## Offline quickstart

Python 3.10+ and SQLite with FTS5 are required. Install dependencies in your own environment; no dependencies or model weights are vendored here.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s portable -p 'test_*.py' -v
python -m unittest discover -s portable/tests -p 'test_*.py' -v
python examples/create_synthetic_input.py demo-input
python portable/process_library.py --manifest demo-input/manifest.json --out demo-output
python portable/verify_production_collection.py --manifest demo-input/manifest.json --collection demo-output --processor-root portable
python portable/search_assets.py demo-output ozone --kind equation --limit 1
python portable/clean_preserved_md.py --collection demo-output --out demo-output/MD_clean
```

The example creates one authored PDF and mock layout without running MinerU. Expected structural outputs: one document, two body blocks, one figure, one equation and five search records. Repeating `process_library.py` validates the published revision and processes zero new documents. Choose a new cleaning output directory on each run. Generated examples are ignored by Git.

Real inputs use a `papers` manifest; each item contains `id`, `pages`, `staged` (PDF path), `sha256`, `layout` (MinerU middle JSON), and `glyph_library` (reviewed mapping JSON; an empty array is valid when no mapping is supplied). Paths are relative to the manifest. The cleaner removes selected publication metadata/reference regions from a derived view and preserves its decisions in a log; it does not perform semantic chunking.

## Outputs and boundaries

Each document package includes `reading.md`, `llm.md`, `llm_blocks.jsonl`, `assets.jsonl`, `captions.json`, `quality.json`, source crops and publication receipts. Collection indexes use SQLite FTS5. `scientific_ready=false` and review flags remain visible. Unverified table/equation transcription is not promoted into the default searchable evidence view.

Composite figures are represented by source crops spanning associated panels and captions; uncertain continuation is explicit. Tables retain their original region image and caption, while available MinerU HTML is stored separately as an unverified transcription candidate.

[54 synthetic tests passed](TEST_RESULTS.md). A separate one-document synthetic execution, resume, integrity check, search and cleaning passed. This does not evaluate OCR accuracy or scientific extraction on real papers. Six source test files requiring research-corpus fixtures are intentionally excluded. Real-data runs and full MinerU model inference were not repeated.

Known limitations: caption/region heuristics need source review; glyph reuse supports embedded CFF outline matches; scanned PDFs need upstream recognition; geometric coverage is not semantic completeness. The two legacy `verify_native_assets.py`/`verify_preservation.py` checks include ozone-specific search probes; prefer the manifest-driven `verify_production_collection.py` for general integrity checks. It certifies integrity only. Do not run Python with `-O`, because existing validators use assertions. One generation process should own a collection at a time; revisions are immutable.

## Optional parser adapter

`scripts/convert_one.py` and `scripts/runtime_threads.py` preserve the original local CPU/MPS adapter. `requirements-parser.in` records its older MinerU 2.0.4 stack separately from the postprocessing requirements. It needs separately provisioned model files, a local `mineru.local.json`, a prepared `runs/` directory, and compatible hardware. The bounded thread adapter additionally requires RapidTable 1.0.5. Model provisioning, installation and inference are not validated in this snapshot. Do not combine the optional parser environment with the lightweight quickstart by default.

## Optional open-literature reference

[Open-literature instructions](examples/OPEN_LITERATURE.md) and [the reference manifest](examples/open_literature.json) identify two separately verified openly licensed articles. They contain attribution, license metadata and short paraphrases; no article PDF or parsed text is bundled. This literature reference was not used by the 54 synthetic tests.

After separately provisioning the optional parser environment, local models and config, a user-downloaded PDF can be passed to the existing adapter:

```sh
mkdir -p runs
python scripts/convert_one.py /path/to/user-downloaded-open-article.pdf --name open_article_demo --device cpu --threads 4
```

This command was not run during packaging. It writes local output under `runs/open_article_demo/`, including `result.json` and `raw/` parser artifacts. To postprocess it, construct a manifest pointing `staged` to that PDF and `layout` to its actual `*_middle.json`, with the PDF hash, page count and an appropriate glyph-library JSON. The runtime directories and downloaded paper remain ignored; source-paper licensing still governs any later redistribution.

## Scope and credit

This snapshot contains selected project-owned workflow code, synthetic tests, a generated-example script and minimal packaging edits. No paper corpus, original Markdown, model weights, production manifests, credentials, prior Git history or runtime collection is included. [SOURCE_VERSION.md](SOURCE_VERSION.md) records the export and changes; [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) distinguishes upstream components. Individual collaborator and AI-assisted development roles should be confirmed before any public portfolio claim. No open-source license is granted by this private snapshot.
