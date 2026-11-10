# MU-PSA 与基线

实现位置：`src/urbannoise/predictors.py`、`src/urbannoise/assignment.py`、`src/urbannoise/experiment.py`。

## 移动预测

`fit_mobility` 只使用时间片 `0..visible_until`。转移计数在 `visible_until` 停止。对参与者 a、目标日内时间 tod、当前位置和提前量 lead：

```
p_time = 该日内时间的历史计数，若为空则退回总频率
p_markov = 从当前位置做 lead 步转移
p = 0.55 * p_time + 0.45 * p_markov
```

若马尔可夫行不可用，则只用时段频率。`validate_distribution` 拒绝负数、非有限值或和不为一的分布。

到达概率不是接受概率。接受概率是参与者属性 `accept_prob`。执行成功还要求真实轨迹在目标时间片落在任务网格上，并由一次接受随机数决定，除非任务已经处于 accepted 或 in_progress。

## 噪声预测

能量 `e = 10^(L/10)`。IDW 在能量域对最多 8 个邻居加权，权重是 `1 / max(distance, 0.35)^2`。距离 = 空间欧氏距离 + 0.55 × 日内循环时间差 + 3.5 × 用地是否不同。

不确定性先用能量方差的 delta method 换成 dB，再与 `0.35 + 0.5 × 最近空间距离` 取最大，并截断到 0.35–15 dB。没有观测时预测 55 dB、标准差 12 dB。

随机森林 40 棵树，样本少于 16 时退回 IDW。标准差是树间标准差，截断到 0.4–15。高斯过程使用固定的 RBF(2.5)+WhiteKernel(1.0)，`optimizer=None`。时间窗内样本数不在 8–220 时退回 IDW。

## 价值与分配

```
unc_norm = clip(uncertainty / max(median, 0.5), 0, 3)
Value = w_u * unc_norm + w_c * (exp(-count) + 0.5 * isolation)
        + w_t * temporal_gap - w_d * duplicate
```

默认权重：不确定性 1.0，覆盖 0.65，时间 0.25，重复 0.8，成本 0.35。

MU-PSA 分数：

```
score = reach * accept * quality * Value - 0.35 * cost
```

`mupsa_constrained` 还要求 reach ≥ 0.22。`mupsa_no_mobility` 只在当前曼哈顿距离不超过半径时用 Value 减成本。`mupsa_no_uncertainty` 与 `mupsa_no_coverage` 通过把对应价值项置零实现。

其他方法：

- random：当前距离可行或到达概率达标时使用随机分数。
- nearest：只看当前距离，分数为负距离。
- greedy：当前距离可行时用 Value 减 0.03 倍距离。
- uncertainty：当前距离可行时用归一化不确定性减 0.03 倍距离。
- min_cost：当前距离可行或到达概率 ≥ 0.22 时，分数为负的成本加 0.12 倍截断距离，再用匈牙利算法在最多 40 个任务上求最小成本。

每人每个目标时间片至多一个任务。预算在规划时预扣。仿真来源的失败任务在允许重规划时退回预算。手工任务不参与这笔退款。

## 因果误差

评估时间片 t 的预测只使用 `slot <= t` 的观测。误差相对干净的 `laeq[t]`，不是相对带测量噪声的观测。覆盖率是评估期内至少成功采样一次的格子比例。

## LinUCB

上下文 10 维：常数、截断的不确定性、价值、到达概率、成本、距离、是否机器、接受概率、预算比例、时间比例。不含真值。训练奖励包含成功、不确定性和成本，并使用仿真 MAE 下降。推理时 `train_bandit=False`。短名单最多 20 对。
