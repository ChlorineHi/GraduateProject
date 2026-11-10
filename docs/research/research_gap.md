# 研究缺口

标签：verified metadata、abstract-only、full-text read、author claim、our interpretation、hypothesis、not yet tested。缺口判断是 our interpretation，不是“文献里不存在”。`graph coverage` 只说明当前 CDRI 项目图里，这个联合问题还没有登记过一个求解方法，而且没有 `paper confirm` 过的 deep 阅读账本。那不是出版空白的证明。

## 已经分开存在的两块

[full-text read] 选哪里测，在已读论文里通常是一个会被执行的设计：

- Krause、Singh 与 Guestrin（JMLR 2008，DOI `10.5555/1390681.1390689`）在高斯过程上放传感器。熵和互信息是不同准则。固定核时，后验方差不依赖观测值，所以开环等于闭环。[author claim]
- Cao、Low 与 Dolan（AAMAS 2013，DOI `10.65109/frmm7982`）把 entropy、mutual information 和 prediction error 分成三个指标。路径由规划器控制。[author claim]
- Nishida 等（IEEE TSP 2022，DOI `10.1109/tsp.2022.3156012`）允许放置区域和估计区域不同，并用均方误差或条件熵。[author claim]
- Verburg 等（EURASIP 2024，DOI `10.1186/s13636-024-00364-4`）最小化声场参数或重建声压的 Bayesian Cramér-Rao bound。传感器由实验者放置。[author claim]
- Alexanderian（Inverse Problems 2021，DOI `10.1088/1361-6420/abe10c`）的设计降低 PDE 反问题的参数不确定性，并假定测量会做。[author claim]

[full-text read] 派给谁，在已读论文里通常优化的不是噪声地图误差：

- Li 等（ToN 2022，DOI `10.1109/tnet.2022.3169180`）在预算和容量下选择能力未知的工人，奖励是样本是否合格。[author claim]
- Simon 等（TCOM 2024，DOI `10.1109/tcomm.2024.3381718`）用报价表示愿意参加，摘要中的结果是任务完成时间。[author claim]
- Wang 等（ICDCS 2018，DOI `10.1109/icdcs.2018.00164`）和 Liu 等（Computer Networks 2019，DOI `10.1016/j.comnet.2019.06.010`；IEEE Access 2019，DOI `10.1109/access.2019.2924184`）选择格子或格子–任务对。读过的部分把参与者写成能提供这些格子的人。
- Huang 等（2026，DOI `10.1007/s42486-025-00202-2`）选择对下游分类有用的子区域，并写明员工会去这些位置。[author claim]
- Zhang 等（2023，DOI `10.3934/mbe.2023533`）在轨迹已知的前提下招募用户。[author claim]

[abstract-only] Zhu 等（DOI `10.1109/jiot.2020.3024833`，Crossref 年 2021）的仓库摘要讨论不同成本下的格子选择。正文没有读到，所以不把它算进“已经处理了人的拒绝”的证据。

## 还没有被这些全文闭合的问题

[our interpretation] 噪声地图上的一次决策同时有五个随机或代价因素：人是否到达、人是否接受、测量噪声、空间相关如何把这一次测量传到其他格子、以及成本是否还在预算内。已读全文分别处理了其中几项，没有一篇在读过的章节里把五者放进同一次噪声地图误差的期望，并且禁止平台改写这个人的未来轨迹。

这不是新颖性证明。撤回预印本 DOI `10.21203/rs.3.rs-4954416/v2`（题名以 WITHDRAWN 开头）已经把移动预测和任务分配写在一起。它被排除，不能引用为方法，也不能反过来用来宣布本项目填补了空白。novelty 在 CDRI idea 卡上保持 unknown。

## 本仓库还没做的计算

[not yet tested] 内部 MU-PSA 是

```
score = reach * accept * quality * Value - 0.35 * cost
```

Value 含归一化不确定性、覆盖、时间间隔和重复惩罚。见 `docs/algorithms/mupsa.md`。它不是互信息，也不是一步期望地图误差。`experiments/results/main/summary.json` 没有这个期望的排名。

[hypothesis] 要补的计算是：对同一批格子–人配对，比较“预测不确定性”和“含到达、接受、测量噪声、空间相关、成本的一步因果 MAE 期望下降”。接受概率在没有接受/拒绝标签时继续仿真。分配结果不能回写未来轨迹。
