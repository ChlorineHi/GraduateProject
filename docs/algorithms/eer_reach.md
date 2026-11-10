# eer_reach

这是本仓库里的一个内部评分，不是一篇已发表方法，也没有被调参去赢得对比。

对一个格子，预测标准差是 `std`，传感器标准差是 `sensor_sigma`。令

`v = std²`，`r = sensor_sigma²`。

一次高斯测量之后，后验方差是 `v r / (v + r)`，方差下降是

`v² / (v + r)`。

代码在 `expected_error_reduction`。分母加了 `1e-12`，避免 v 和 r 同时为 0。

`eer_reach` 只在到达概率不小于 0.22 时给分：

`P(reach) * P(accept) * quality * (v² / (v + r)) - 0.35 * cost`

0.35 沿用 MU-PSA 里已有的成本系数，没有为了这次对比再搜索。

这个式子只描述被测那一个格子的方差下降。它没有用高斯过程的空间协方差去更新邻居，所以它不是 Krause 等人的互信息，也不是分类主动学习里的 expected error reduction。消融 `eer_no_reach`、`eer_no_accept`、`eer_no_cost` 分别去掉到达概率、接受概率和成本项。
