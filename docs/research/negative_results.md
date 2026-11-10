# 负结果

数字来自 2026-11-10 的 `scripts/run_phase2_episodes.py`。协议名 `mae_available_at_t`。公平合成实验是 8×8 网格、2 天、每天 6 个时间片、3 个种子、预算 4/8/12。真实移动实验每个子集 2 个种子、预算 8。没有在看到结果后改权重。

## 公平合成协议

- complex、预算 4：`reach_random` 的 MAE 是 9.2482±1.6678，`eer_reach` 是 9.4633±1.5758，`mupsa` 是 9.5066±1.4770。`eer_reach` 和 `mupsa` 都不是这一格的赢家。
- complex、预算 12：`reach_random` 是 9.1679±2.2074，`eer_reach` 是 9.2940±1.6979，`mupsa` 是 9.7169±1.0500。两者都不是赢家。
- regular 的三个预算上 `eer_reach` 平均 MAE 最低，但 `mupsa` 仍然不是最低。预算 8 时 `mupsa` 是 11.2243±1.8611，`eer_reach` 是 10.0807±1.9651。
- `nearest` 在 regular 上成功任务均值是 0 或 0.33。它被保留为弱基线。
- `uncertainty`、`greedy`、`bandit` 在三个预算上的 MAE 相同，因为它们没有随着预算增加而完成更多成功采样。LinUCB 只训练了 2 个回合。这不能外推成“LinUCB 在更长训练后仍然无效”。

## 消融

regular、预算 8、3 个种子：

- `eer_reach` 9.7580±2.5184
- `eer_no_accept` 9.4837±2.7795，比完整式子更低。接受概率这一项在这个切片上没有降低误差。
- `eer_no_cost` 与 `eer_reach` 相同。成本项没有改变选择。
- `eer_no_reach` 12.0173±1.3196，去掉到达概率后变差。

## 真实移动

- YJMob dataset1，day 0–1，10 个真实用户，窗口内 125 行：`min_cost` 10.1624±4.8982 最低，`eer_reach` 10.8701±4.8512，`mupsa` 10.9720±4.3656。
- YJMob dataset2，day 0–1，10 个用户，114 行：`random` 9.6565±1.7679 最低，`eer_reach` 11.6025±1.4227 最高。
- YJMob dataset2，day 60–61，10 个用户，134 行：`nearest` 8.0702±0.5932 最低，`eer_reach` 9.8439±0.2870 最高。
- GeoLife，8 个用户（请求 10 个，窗口内只有 8 个达到最少点数），2008-11-01 与 2008-11-02，165 行：`min_cost` 12.2390±2.5102 最低，`eer_reach` 13.4918±1.0580。

## 真实噪声

France 的小时箱留出：输入 114182 行，训练 4000，测试 1500，MAE 18.2598，RMSE 22.4131，R² -0.3516。R² 为负，说明比用均值预测更差。这不是全城连续场的 MAE。Luxembourg：输入 204，训练 143，测试 61，MAE 15.5243，RMSE 20.7696，R² -0.4318。

## 不能做的拼接

GeoLife 原始时间止于 2012-07-27。NoiseCapture 各国 summary 的起始时间都晚于这个日期。`overlap_report` 的 `feasible` 是 false。Fully-Real 没有构造联合回合。
