# The outcome audit's scripts and small outputs

Independent checks of the stink-bid study's results of record (commit eee2ddf), run after the verdicts. Each
folder is one agent's working directory: its own code (written from the pre-registration, without importing the
functions it checks) and its small outputs. Large intermediates (parquet, pickles, per-coin tables above 100 KB, and
copies of the repo's modules at earlier commits) were left out; the scripts regenerate them from `data/stinkbid/`.

- `audit/`: the seven lenses and the verifiers of workflow 1.
  - `flip_rest`: H1, H2R, Holm, the gates and A2.7 (recomputed).
  - `h4_levels`: H4.
  - `engine_spot`: the raw 1-minute check of every bid, fill, exit and alert buy (`fullcheck.py` reruns it).
  - `h1fair`: twin fairness, decompositions and bad-print checks.
  - `answermap`: the answer against §11 and §12.
  - `h1lens`: inference and robustness.
  - `lookahead`: look-ahead and survivorship.
  - The other folders verify single findings.
- `audit2/`: the follow-up (read the record from git).
  - `critic`: the completeness critic. It covers what one flip made, the 2023-26 half, the D7 rebuild with its
    halves and single events, the alert-entered flip and bid lives.
  - The other folders verify single findings.

Paths inside the scripts point to the session's scratch folders. Run them from the repo root after adjusting the
output paths. The report (`analysis_2026/reports/Stink bids.md`, section 5) summarizes what they found.
