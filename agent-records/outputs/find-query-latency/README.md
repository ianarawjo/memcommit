# Find/Query GPT-5.6 family smoke matrix

Run: `20260811-gpt-5.6-family-none-low-medium-smoke-v1.json`

This is one sequential repetition of six frozen Task 3 cases per condition.
All 54 provider calls completed, all 27 Find responses passed the production
JSON contract, and no provider error occurred. Provider time totalled 357.97
seconds; the campaign ran from 13:42:38Z to 13:48:38Z on 2026-08-11.

## Find

Times are medians and maxima over two real searches plus one unsupported
search. Historical and study-selected recall are means over only the two real
searches. The historical rows are study evidence, not a gold relevance set.
`Empty` reports whether the unsupported search returned no primary match.

| Model | Effort | Median s | Max s | Historical recall | Study-selected recall | Empty |
|---|---:|---:|---:|---:|---:|:---:|
| Sol | none | 4.94 | 5.72 | 0.60 | 0.375 | yes |
| Sol | low | 11.68 | 15.67 | 0.60 | 0.500 | yes |
| Sol | medium | 15.16 | 15.58 | 0.80 | 0.500 | yes |
| Terra | none | 4.01 | 4.80 | 0.70 | 0.375 | yes |
| Terra | low | 7.70 | 8.57 | 0.80 | 0.625 | yes |
| Terra | medium | 8.88 | 10.56 | 0.70 | 0.500 | yes |
| Luna | none | 3.93 | 5.48 | 0.20 | 0.250 | yes |
| Luna | low | 9.14 | 12.01 | 0.60 | 0.375 | yes |
| Luna | medium | 12.06 | 14.99 | 0.60 | 0.250 | yes |

Terra/low is the strongest first candidate for Find: it tied the best
historical recall, led study-selected recall, and was roughly twice as fast as
Sol/medium. Terra/none is the latency candidate, but the reference-recall loss
means it should not replace Terra/low from this smoke run alone. Luna/none is
fastest but failed to produce any primary result for one real search.

## Query

Times are medians and maxima over synthesis, narrow, and unsupported questions.
Concept recall is a transparent regex diagnostic audited against every raw
answer. The version-2 rescore corrected expression-level false negatives only;
it did not change provider outputs or timing.

| Model | Effort | Median s | Max s | Concept mean | Concept min | Invented day count |
|---|---:|---:|---:|---:|---:|:---:|
| Sol | none | 6.16 | 6.75 | 1.000 | 1.000 | no |
| Sol | low | 8.30 | 9.91 | 1.000 | 1.000 | no |
| Sol | medium | 7.05 | 9.03 | 1.000 | 1.000 | no |
| Terra | none | 4.43 | 5.69 | 1.000 | 1.000 | no |
| Terra | low | 4.93 | 7.56 | 1.000 | 1.000 | no |
| Terra | medium | 4.99 | 6.02 | 1.000 | 1.000 | no |
| Luna | none | 3.55 | 7.00 | 0.889 | 0.667 | no |
| Luna | low | 3.21 | 6.32 | 0.889 | 0.667 | no |
| Luna | medium | 4.11 | 5.86 | 0.889 | 0.667 | no |

Terra/none is the strongest first candidate for ordinary Query: it retained all
audited concepts and the unsupported-answer boundary while giving the lowest
median among the full-coverage conditions. Luna was slightly faster at the
median but omitted the transmission-screen boundary in the narrow question.

## Boundary

This smoke matrix has no repeated samples, so small timing differences are not
stable estimates. A product pin should follow a repeated confirmation run,
especially for Find, and should preserve the raw-answer audit rather than use a
latency-only threshold.
