# Sentiment external benchmark protocol v1

This file is the execution contract for `artifacts/benchmark/v1`. The source
bytes are stored and hashed before decoding; UTF-8 decoding is strict, rating
3 is excluded, and 1/2 versus 4/5 maps to negative versus positive. Original
review text is never rewritten.

Exact duplicate keys use NFC plus collapsed Unicode whitespace. Conflicting
exact labels are excluded. For text with at least 20 code points, connected
5-gram set Jaccard at least `0.85` forms a group; MinHash uses 256
permutations, seed `20260905`, and LSH `(32, 8)`, followed by exact checks.
Groups are indivisible. Exposure-connected groups go to development first.
Near-duplicate shingles use the NFC/whitespace key, never rewritten input.
MinHash update_batch and shared permutation copies retain the same signatures.
An independent, lossless prefix-filtered exact Jaccard audit checks all selected
splits and registered exposures. Missed links merge groups and trigger deterministic
reallocation before any engine evaluation. Reserve is outside this exact audit.
The abandoned all-pairs run created no split or score. This clarification and
implementation repair are frozen before the first completed benchmark.

Splitting is deterministic with seed `20260905`, targets development 4,000,
selection 2,000, final 2,000, and reserve remainder. Rating proportions are
matched by exact `Fraction` cost comparisons, dividing each squared rating
deviation change by max(target rating count, 1), as in the original plan.
Selection/final must contain 1,800–2,200 rows and at least 40% of each class.
Source order is numeric line
order within each output file.

The runner passes only `{id, text}` to an isolated candidate worker. Every row
has one prediction, including timeout and analysis errors. Metrics use a 2x4
matrix, Wilson accuracy intervals, and paired cluster bootstrap intervals with
NumPy PCG64 seed `20260906` and 2,000 repetitions.

The sole candidate for this run is the unchanged current sentiment engine
snapshot, modifiers enabled. Selection is unused. Development on/off results
are descriptive and do not change the candidate. Final runs on/off once and
reports paired group intervals even when the candidate equals baseline.
Targets are Accuracy >= 0.80, binary Macro F1 >= 0.80, each class recall >= 0.75,
and group bootstrap Accuracy lower 95% bound >= 0.75. Baseline improvement is
separate (identical candidate implies zero difference), not a target.
Neutral and analysis errors remain in the denominator. Original star polarity
is the gold label; it is a noisy proxy for shopping-review sentiment.
Final source, split, exposure, protocol, engine, evaluator and environment hashes
must match the frozen release. A final attempt consumes its one-use marker;
code or rule changes after final need a new, unexposed benchmark.

Protocol changes require a new benchmark version and a new protocol hash.
