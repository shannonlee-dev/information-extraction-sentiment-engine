# External sentiment benchmark results

The v1 benchmark runner and evaluation contracts are implemented, but no
external source bytes or final score are committed yet. A result is valid only
after the source SHA-256, protocol hash, exposure register, split hashes, and
candidate release manifest are frozen.

Prepare a source snapshot with:

```bash
python3 -m scripts.prepare_sentiment_benchmark \
  --source artifacts/benchmark/v1/raw/naver_shopping.txt \
  --source-manifest artifacts/benchmark/v1/source.json \
  --protocol docs/evaluation/sentiment-protocol.md \
  --exposures docs/evaluation/exposure-register.jsonl \
  --output artifacts/benchmark/v1 --seed 20260905
```

Create and verify a candidate snapshot before running development, selection,
or final evaluation. Final evaluation must use `--release-manifest`; candidate
and modifier overrides are rejected in that mode.

No Accuracy, Macro F1, confidence interval, or pass/fail claim is made until
the final split has been executed and its ID, group, and manifest checks pass.
