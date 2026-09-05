# Sentiment external benchmark protocol v1

This file is the execution contract for `artifacts/benchmark/v1`. The source
bytes are stored and hashed before decoding; UTF-8 decoding is strict, rating
3 is excluded, and 1/2 versus 4/5 maps to negative versus positive. Original
review text is never rewritten.

Exact duplicate keys use NFC plus collapsed Unicode whitespace. Conflicting
exact labels are excluded. For text with at least 20 code points, connected
5-gram set Jaccard at least `0.85` forms a group; MinHash uses 256
permutations, seed `20260905`, and LSH `(32, 8)`, followed by exact checks.
Groups are indivisible. Exposure-connected groups go to development.

Splitting is deterministic with seed `20260905`, targets development 4,000,
selection 2,000, final 2,000, and reserve remainder. Rating proportions are
matched by exact `Fraction` cost comparisons. Source order is numeric line
order within each output file.

The runner passes only `{id, text}` to an isolated candidate worker. Every row
has one prediction, including timeout and analysis errors. Metrics use a 2x4
matrix, Wilson accuracy intervals, and paired cluster bootstrap intervals with
NumPy PCG64 seed `20260906` and 2,000 repetitions.

Protocol changes require a new benchmark version and a new protocol hash.
