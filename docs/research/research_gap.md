# 研究缺口

标签：Agent Interpretation。依据是 2026-11-10 的 CDRI landscape 运行 `20261110-013339-joint-sampling-location-and-pa`（537 条去重记录，来源 arXiv、Crossref、DBLP、OpenAlex、Semantic Scholar，退出码 0）以及四篇已入库文献的书目字段。全局阅读账本 `ledger` 行数是 0，所以这里不把摘录升级成“方法节已通读”。

## 已看到的分工

- Verified Fact（书目，OpenAlex `pub_status=published`）：Krause, Singh, Guestrin, 2008, *Near-Optimal Sensor Placements in Gaussian Processes: Theory, Efficient Algorithms and Empirical Studies*, JMLR, DOI 10.5555/1390681.1390689。摘录没有在这次写入中重读。已知的方法差异是：传感器是部署上去的，不是一个可能拒绝任务的人。
- Verified Fact（书目，`pub_status=preprint`）：Mussmann 等, 2022, *Active Learning with Expected Error Reduction*, arXiv:2211.09283。磁盘上有实验节摘录（约第 387–520 行）。摘录讨论的是图像分类和标签被观察到之后的误差。阅读账本没有 confirm 记录。
- Verified Fact（书目，published）：Li, Zhao, Yu, Cheng, Lv, 2022, *Harnessing Context for Budget-Limited Crowdsensing With Massive Uncertain Workers*, IEEE/ACM Transactions on Networking, DOI 10.1109/tnet.2022.3169180。
- Verified Fact（书目，published）：Cao, Low, Dolan, 2013, *Multi-robot informative path planning for active sensing of environmental phenomena: a tale of two algorithms*, DOI 10.65109/frmm7982。磁盘上有引言摘录。

## 缺口

这些工作分别处理传感器放置、分类查询、众包工人不确定性或机器人路径。本系统要同时处理：人可能到不了格子、可能拒绝、测量有噪声、预算有限，而且评价的是决策时刻只能看见已有观测的噪声图误差。CDRI 的 transfer check 把“查询标签一定被观测到”和“任务是分类”标成 violated。因此不能把分类 EER 或 GP 互信息的代码直接当成噪声任务分配。

本仓库没有证明这个组合是新的。idea 卡把 novelty 标成 unknown。
