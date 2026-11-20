# Lacuna AU

*Lacuna* is Latin for "a gap". This tool reads the Australian Constitution, Commonwealth law,
State law and case law on one topic, then uses local AI agents to find:

- **Conflicts** between levels of law (s 109 inconsistency, gaps, contradictory definitions)
- **Loopholes**, meaning ways the law can be gamed or avoided
- **Problems shown up by case law**, such as provisions read down, conflicting
  interpretations, or criticism from judges
- **Council local laws** that exceed their power or clash with State law (see below)
- **Common law vs statute**: judge-made rules that legislation overrides, codifies badly or
  leaves uncertain, conflicting lines of cases between States, and doctrines that can be
  used to avoid a statutory duty

Every finding cites its sources and is checked by a sceptical **verifier** agent. Findings it
can't back up are marked as rejected. The output is a starting point for research,
**not legal advice**.

It runs entirely on your PC through **LM Studio**. Only the law itself is downloaded.

## How it works

```
Open Australian Legal Corpus ──ingest──> topic documents (jsonl)
                                   │
                         chunk + embed (LM Studio)
                                   ▼
                          Chroma vector index
                                   │
   planner ─> questions ─> conflict / loophole / precedent / common_law / local_law agents ─> verifier
                                                                       ▼
                                                         reports/<topic>_report.md
```

## Setup

1. In LM Studio, download:
   - Chat model: **Qwen3 8B** (GGUF, Q4_K_M), about 5 GB and fits fully on an 8 GB RTX 3070
   - Embedding model: **nomic-embed-text-v1.5**
2. Load both and start the server (Developer tab → *Start Server*, port 1234).
   Set the chat model's context length to at least **16k**.
3. Install:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Check the model names in `config.yaml` match LM Studio:
   ```bash
   python -m lacuna.cli check
   ```

## Run

```bash
python -m lacuna.cli ingest    # download and filter the corpus (first run is a multi-GB download)
python -m lacuna.cli refilter  # optional: re-apply topic filter to downloaded docs (no re-download)
python -m lacuna.cli index     # chunk and embed
python -m lacuna.cli analyse   # agents + verifier -> reports/
python -m lacuna.cli report    # rebuild the .md and .pdf from saved findings
# or all three steps:
python -m lacuna.cli all
```

Run a single agent: `python -m lacuna.cli analyse --agents loophole`

Ask your own questions instead of letting the planner choose (or list them under
`analysis.questions` in `config.yaml`):

```bash
python -m lacuna.cli analyse -q "How can landlords avoid the no-grounds eviction rules?" -q "Does the NSW bond scheme conflict with Commonwealth law?"
```

## Council local laws

Council laws are not in the main corpus, so you list the ones you want:

1. Copy `local_laws.example.yaml` to `local_laws.yaml`.
2. For each council, add links to its local-law PDFs or pages, and/or a folder of files you
   downloaded yourself.
3. Run `python -m lacuna.cli local`, then `python -m lacuna.cli index`.

The `local_law` agent then tests each council law against the State Acts that empower it
(beyond power, inconsistency, unreasonableness) and compares councils with each other.
Scanned PDFs with no text layer are skipped with a warning (OCR is not supported yet).

## Choosing a topic

Edit the `topic` and `corpus.jurisdictions` sections of `config.yaml`. Jurisdiction values
in the corpus include `commonwealth`, `new_south_wales`, `victoria`, `queensland`,
`western_australia`, `south_australia`, `tasmania` and `norfolk_island`.
Start small: one topic, Commonwealth plus one State.

## Limits

- An 8B model will produce false positives. The verifier filters many of them, but a person
  still needs to check every finding.
- For better quality, set `verifier_model` to a larger model (e.g. Qwen3 14B Q4 with
  partial GPU offload). It's slower but more sceptical.
- Council laws must be listed by hand in `local_laws.yaml`.

## Roadmap

- [ ] Direct fetchers for legislation.gov.au and the state legislation sites (current versions)
- [x] Council local-law ingestion (manual list)
- [ ] OCR for scanned council PDFs
- [ ] Pairwise provision comparison for s 109 analysis
- [ ] Optional QLoRA fine-tune on verified findings
