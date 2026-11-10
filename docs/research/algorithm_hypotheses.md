# 算法假设

状态一律是 hypothesis，并且 not yet tested。没有一条已经在 `experiments/results/main/summary.json` 里被计算过。MU-PSA 不是这些假设的实现，也不是已发表的新方法。

CDRI idea id：`idea:expected-map-error-not-predictive-uncertainty`。`ideate validate` 没有报错。

## H1. 不确定性排序和期望误差下降排序不同

[hypothesis] 在固定的合成回合里，按预测不确定性排列格子–人配对，和按一步期望因果 MAE 下降排列，选中的配对不同。期望下降要乘上到达概率和接受概率，并计入测量噪声和空间相关。成本进入可选集合或作为分母，不能在比较时丢掉。

[not yet tested] 否定条件：在预先登记的每个预算和种子上，两个排序选中同一对；或者所谓期望下降的排序没有使用到达、接受、噪声、相关和成本。

## H2. 难到达的高不确定性格子会浪费预算

[hypothesis] 只在当前距离可行的人里最大化预测不确定性，在至少一个“高不确定性格子很难到达”的预算上，因果地图 MAE 高于最大化上述期望下降的策略。

[not yet tested] 否定条件：在预先登记的种子和预算上，只要到达概率并不处处相同，不确定性策略的因果 MAE 总是小于或等于期望下降策略。

已有的局部结果不能代替这次比较。[verified metadata of a local file] regular、预算 24，5 个种子的平均因果 MAE：不确定性 6.852，MU-PSA 6.232，最小成本 4.939（`experiments/results/main/summary.json`，四舍五入到三位小数）。MU-PSA 不是 H2 里的期望下降策略。最小成本更低，只说明当前启发式在这个预算上不是最好，不证明 H2。

## H3. 改写未来轨迹会改变实验回答的问题

[hypothesis] 把某个人存储的未来轨迹改成经过被分配的格子，会同时改变到达指示和因果 MAE。机会式规则是使用到达概率，留下原始轨迹。

[not yet tested] 否定条件：改写后的轨迹、到达指示和因果 MAE 都与不改写相同。

[full-text read] [author claim] Zhang 等（DOI `10.3934/mbe.2023533`）的结论把“用户轨迹已知”写成招募的前提。那是他们的假设。[our interpretation] 它不能被实现成“平台把轨迹改成任务路径”。Cao、Low 与 Dolan 以及 JAIR 2009 的路径是机器人被控制后执行的路径，也不是一个人未被改写的未来轨迹。

## 假设会失效的条件

这些条件来自 idea 卡的 fails_if，仍是 hypothesis：

- 场没有空间相关，一次测量不改变其他格子。
- 每个候选的到达和接受都接近 1，执行不确定性消失。
- 预测方差已经是同一噪声模型和同一执行概率下的精确期望平方误差。
- 以后出现真实接受/拒绝标签，而现在的仿真接受模型偏差很大。

## 不能直接搬的算法

`transfer check` 在写入项目事实之后：

- [hypothesis] 分类期望误差下降（arXiv:2211.09283）的假设 `the-queried-label-is-observed` 和 `the-task-is-classification` 被标成 violated。这里的查询不是分类标签，选中的人可能不接受。数据集没有接受/拒绝标签。
- [hypothesis] 高斯过程互信息（DOI `10.5555/1390681.1390689`）的假设 `candidate-locations-are-actually-instrumented` 被标成 violated。失败条件 `design-is-not-executed` 被标成 present。选中格子只有在有人到达并接受时才会被测到。
- [our interpretation] CAWS（DOI `10.1109/tnet.2022.3169180`）在签名里把奖励写成给定上下文的 Bernoulli，并且“选中工人就会产生观测”。这优化的是样本是否合格，不是地图误差。

`compare methods` 的 structural similarity（互信息对期望误差下降 0.257，互信息对 CAWS 0.08）是检索辅助。CLI 注明它不是迁移成功的证据。
