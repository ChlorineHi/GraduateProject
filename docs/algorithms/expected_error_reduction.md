# Expected error reduction (`eer`)

`eer` is an extra assignment method. MU-PSA, LinUCB, min-cost, random, nearest, greedy, and uncertainty are unchanged.

The estimator is a heuristic. It approximates how much one new observation would shrink a variance proxy for squared reconstruction error. It does not read the hidden noise field. It is not mutual information, it is not a Gaussian process conditioned on the observation set, and it has no `(1 - 1/e)` guarantee.

Pass-by probability and acceptance stay separate. `P(reach)` is the probability the participant is at the cell. `P(accept)` is the participant attribute `accept`. The code does not copy one into the other.

## Formula as implemented

Constants in `src/urbannoise/information_gain.py`:

- `ell = LENGTH_SCALE = 2.5` grid cells
- `tau^2 = OBS_NOISE_VAR = 1`
- `eta = DUPLICATE_PENALTY = 1`
- `lambda = weights["cost"]`, default `0.35`
- reach gate `min_reach`, default `0.22` (the existing `allocate` default)

For cells `i` and candidate `c` in the supplied variance vector, with grid coordinates `x = id % width` and `y = id // width`:

```
d(i, c) = Euclidean distance between the two cells
rho(i, c) = exp(-0.5 * (d(i, c) / ell)^2)

raw(c) = (v_c / (v_c + tau^2)) * sum_i rho(i, c)^2 * v_i
expected_error_drop(c) = exp(-eta * duplicate_c) * raw(c)

score(a, c) = P(reach_ac) * P(accept_a) * quality_a * expected_error_drop(c) - lambda * cost_a
```

`raw(c)` is the sum, over the supplied cells, of the variance removed by one Gaussian conditioning step if the covariance were `rho(i, c) * sqrt(v_i * v_c)` and the new observation had noise variance `tau^2`. Existing observations affect the score only through the marginal variances `v`. The factor `exp(-eta * duplicate_c)` is an extra revisit penalty, not part of that Gaussian step. `duplicate is None` leaves the penalty at 1.

A pair is feasible only when the agent is online and `P(reach_ac) >= min_reach`. Otherwise the pair stays at the infeasible sentinel `-1e9` and is not written as a finite `eer` score. The shared greedy selector then stops at the first score below 0, so a negative `eer` score is not assigned.

Two sources of `v`, same drop and same pair formula:

- `allocate(..., method="eer")` sets `v = max(unc_norm, 0)^2` after replacing non-finite uncertainty with 0. The sum is over the candidate list only. `unc_norm` is the uncertainty channel already on the `allocate` interface.
- `eer_pair_scores_from_observations` sets `v = std_IDW^2`. `std_IDW` comes from `predict_idw` on the observation dict (neighbor-weight dispersion in the energy domain, plus that function's distance floor and clip). Query index `i` is grid id `i` in row-major `(x, y)` order. The optional `noise_field` argument is deleted and not read.

Worked check used by the tests. Cells 0 and 1, `width = 4`, so `d = 1`, `v = [4, 1]`, `duplicate = 0`:

```
rho(0, 1)^2 = exp(-0.16)
raw(0) = 0.8 * (4 + exp(-0.16))
raw(1) = 0.5 * (4 * exp(-0.16) + 1)
```

## Complexity

Let `A` be the number of agents and `C` the number of cells in the variance vector.

- The kernel matrix and the sum that produces `raw` are `Θ(C^2)` time and `Θ(C^2)` memory.
- Pair scores are `Θ(A C)`.
- Manhattan distances are `Θ(A C)`, as for every other method.
- Greedy selection sorts the pairs, `Θ(A C log(A C))`.
- The observation entry point calls IDW first. For `Q` query cells and `N` observations that builds a `Q × N` distance matrix, `Θ(Q N)` time and memory, then the `Θ(Q^2)` drop when every query is a candidate.

Other assignment methods do not build this kernel.

## Failure cases

- The covariance `rho * sqrt(v_i v_c)` is assumed, not fit. If the length scale 2.5 is wrong for the field, nearby and distant cells are mis-ranked. This length matches the fixed RBF length of the GP baseline only as a number. `eer` does not call that GP and does not condition on observation locations beyond the variances it is given.
- IDW standard deviation is a clipped heuristic (neighbor disagreement and distance). The observation-path variance inherits that. It is not a calibrated posterior.
- On the `allocate` path, `unc_norm` may already have been median-scaled and clipped to `[0, 3]` by `cell_features`. Squaring it does not recover dB². `tau^2 = 1` is in whatever units `v` has, so the same constant means different things on the two paths.
- Cells left out of the candidate list are absent from the sum. Dropping a region from `grids` changes the score of the cells that remain.
- Each candidate is scored as if it were the only new observation. One `allocate` call can still return several pairs. Overlapping drops are counted separately, so a batch can look more informative than a joint design would.
- The revisit penalty is only as good as the caller-supplied `duplicate` vector. Zeros disable it. Non-finite entries and negative entries are treated as zero, so a negative duplicate cannot increase the drop. A mild penalty does not by itself exclude a cell; `eta = 1` and a duplicate of 2 multiplies the drop by `exp(-2)`.
- `P(reach)` below `min_reach` (default 0.22) is infeasible even if that pair has the largest ungated product. A participant above the gate can still fail to arrive. The residual failure is only the remaining factor `P(reach)` in the product.
- Acceptance, quality, and cost are the stored participant attributes. A wrong `accept` scales every one of that agent's drops. High reach does not raise `accept`.
- If `lambda * cost` exceeds the scaled drop, the formula is negative and the greedy floor does not assign it. Budget `<= 1e-9` or `cap <= 0` returns no assignments before scoring. A positive score whose cost exceeds the remaining budget is skipped by the existing selector.
- Offline agents are skipped by the shared loop.
- The selector still gives each agent and each cell at most one assignment per call.
- Because the noise field is not an input, a bias that does not appear in the variance proxy is invisible. Changing future truth while observations stay fixed does not change the score. That is required. It also means `eer` cannot chase an error it cannot see.
- `experiment._plan_slot` may call `allocate` with `method="eer"` without further changes. The number it stores as task value is still `combine_value` output. The assignment score is the `eer` formula above. Those two numbers are not the same quantity.
- Memory is the practical limit. One `C × C` float64 kernel is `8 C^2` bytes (about 0.5 MB at 16×16, about 128 MB at 64×64). Distance and squared-correlation temporaries add a small multiple of that.

## Files

- `src/urbannoise/information_gain.py` — variance proxy, drop, pair score, observation entry point
- `src/urbannoise/assignment.py` — `method="eer"` inside `_score_matrix`, called by the existing `allocate`
- `src/urbannoise/predictors.py` — `predict_idw` supplies the observation-path standard deviation; that function is not modified
- `tests/test_information_gain.py` — truth independence, reach gate, zero budget, duplicate penalty
- `docs/algorithms/expected_error_reduction.md` — this note
