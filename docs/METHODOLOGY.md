# Methodology

Plain-English description of every statistical method in `backend/app/stats/`. All of it is
deterministic Python: the LLM never computes a number; it only reads these outputs.

**All data is synthetic.** The numbers quoted below come from the synthetic dataset in
`backend/scripts/generate_data.py`.

## 1. The data

A daily panel: 20 US DMAs (geos) x 730 days. For each geo and day we have spend on four
channels (Meta, Google Search, TikTok, Billboard) and total conversions. Conversions are one
number per geo and day; the job is to work out how much of it each channel caused.

## 2. Media transforms (`transforms.py`)

- **Adstock** — advertising keeps working for a while after the money is spent. Today's
  "pressure" is today's spend plus a fraction (`decay`) of yesterday's pressure.
- **Hill saturation** — the tenth dollar works better than the millionth. Pressure is passed
  through `x / (x + K)`, which flattens out as spend grows. `K` is the level at which the
  channel delivers half its maximum.
- Pressure is measured per unit of geo size and relative to the channel's normal
  ("reference") spend, so New York and Sacramento are on the same scale.

*Limitation:* decay and `K` are **fixed priors** stored on the `channels` table. In the
synthetic world they equal the true values; in a real deployment they would come from a
marketing-mix model and would be wrong by some amount, which would bias the estimates.

## 3. Response model (`response.py`)

For each **trailing 42-day window** (one every 7 days) we fit one regression for all four
channels together:

    conversions per capita  =  geo effect + day effect + sum over channels (beta x pressure per capita)

- *Day effects* soak up everything that hits all geos at once: seasonality, weekdays,
  holidays, a national news story.
- *Geo effects* soak up permanent level differences between geos.
- What is left to identify `beta` is **geo-specific variation in spend**: one DMA getting a
  budget pulse while the others do not. That is the same logic a geo experiment uses, just
  observational.
- Per-capita scaling matters. Without it, big geos have bigger seasonal swings, and that
  swing leaks into the channel estimates.

`beta` is turned into **iROAS at reference spend**: incremental revenue per dollar if a geo
spent the channel's reference amount. Fixing the spend level means that spending more in Q4
(and therefore hitting saturation) does not look like drift.

The standard error comes from ordinary least squares (residual variance x (X'X)^-1, with
degrees of freedom reduced for the fixed effects). The confidence interval is +/-1.96 SE.

*Limitations:* OLS errors assume independent, equal-variance noise; real data has serial
correlation, so the intervals are too narrow. Channels whose spend barely varies across
geos (billboards bought in national flights) get wide intervals. Only one outcome metric.

## 4. Ledger conversion

A lift test reports iROAS **at the spend level during the test**. To compare it with the
rolling estimates we convert it to the reference-spend basis using the same priors:
`factor = (iROAS per beta at reference spend) / (iROAS per beta realised during the test)`.
The estimate, CI and SE are all multiplied by that factor.

## 5. Drift detection (`drift.py`)

Three detectors look at the series of window estimates:

1. **PELT changepoints** (`ruptures`, least-squares cost). The series is divided by its
   median standard error so the penalty (12) is in noise units; segments must be at least 3
   windows long. For each break we report the date, the mean before and after, the relative
   change, the direction, and a shift z-score (difference / (median SE x sqrt 2)).
   Only the latest changepoint **after the latest ledger test** is "relevant": a change that
   happened before the test is already baked into the evidence.
2. **CUSUM** (second opinion). Each window is converted to a z-score against the reference
   level — the ledger value if there is one, otherwise the mean of the first six windows —
   and accumulated in two one-sided sums with allowance k = 1. An alarm is active when either
   sum exceeds h = 8. The threshold is high on purpose: overlapping windows share data, so
   consecutive z-scores are correlated and a textbook h ~ 5 fires too often.
3. **Posterior shift**. Is the current estimate compatible with the latest ledger entry?
   `z = (current - ledger) / sqrt(se_current^2 + se_ledger^2)`; |z| > 2.58 (99%) is a
   significant contradiction. We also report whether the estimate sits outside the ledger
   CI. (This is a frequentist test that plays the role of "does the posterior still cover
   the new data" — hence "Bayesian-ish".)

**Confidence score** = 0.4 x min(1, changepoint z / 4) + 0.3 x min(1, CUSUM / h)
+ 0.3 x min(1, |posterior z| / 4). A transparent weighted vote, not a probability.

*Limitations:* the weights and thresholds were tuned on synthetic data (checked across seeds
1-6 and 42). A 42-day window means a sudden change needs roughly 2-4 weeks to show up.
Gradual drift is harder than a step change. With a biased reference, CUSUM eventually
drifts toward an alarm even on a stable channel; the evidence-age rule usually fires first.

## 6. Staleness (`staleness.py`)

| Status | Rule |
|---|---|
| RED | drift confidence >= 0.7, **or** significant posterior shift |
| YELLOW | no test on record, latest test older than 180 days, or confidence in [0.4, 0.7) |
| GREEN | otherwise |

Score (0-100) = 40 x evidence-age fraction (age / 365, capped at 1; 1 with no evidence)
+ 60 x drift confidence, floored at 70 for RED and 35 for YELLOW. Every status carries a
list of machine-readable reasons (`drift_detected`, `posterior_shift`, `no_evidence`,
`evidence_ageing`, `weak_drift`, `fresh`).

## 7. Retest design (`retest.py`)

A **geo holdout**: switch the channel off in some geos, keep it on in matched controls.

1. **Matching.** Correlate per-capita daily conversions over the last 90 days. Repeatedly
   take the two most correlated unused geos as a pair (5 pairs by default). A seeded coin
   flip chooses which of the two is the holdout.
2. **Duration.** Build the pre-period difference series `holdout - r x control` (r = size
   ratio) and take its standard deviation. The lift estimate's SE is about
   `sd x sqrt(1/n + 1/90)`. The expected daily loss in holdout geos is the current effect x
   their media pressure. The test must detect a change of `target_mde` (default 20%) in that
   loss at alpha = 0.05, power = 0.8; we solve for `n` and clamp to 14-56 days. If 56 days
   is not enough, the plan is marked `feasible = false` and the achieved MDE is reported.
3. **Cost.** Expected lost conversions = daily loss x days; cost = lost conversions x $60.
   Spend saved in the holdout geos is reported separately (it partly offsets the cost).

*Limitations:* pairs are matched on correlation only (not level or trend); adstock carry-
over after the pause is ignored; assumes the current estimate holds for the whole test;
no spill-over between neighbouring DMAs.
