# 证据链

每一环只使用它自己的标签。后面的环不能把前面的 author claim 升级成本项目的实验结果。

## 1. 信息指标和预测误差可以被分开

[full-text read] [author claim] Krause、Singh 与 Guestrin，JMLR 2008，DOI `10.5555/1390681.1390689`。读的是 jmlr.org 的出版 PDF。熵准则会把点放在边界。互信息看的是已选位置对未选位置的解释。固定核时条件方差不依赖观测值，开环设计和闭环设计相同。`(1-1/e)` 量级的贪心保证针对互信息。pypdf 抽出的公式有乱码，不把抽出的式子当成精确公式。

[full-text read] [author claim] Cao、Low 与 Dolan，AAMAS 2013，DOI `10.65109/frmm7982`。读的是 OpenAlex 指向的 arXiv PDF 1302.0723。实验分开报告 entropy、mutual information 和 prediction error。熵方法在熵指标上更好或至少不差，互信息方法在互信息指标上更好或至少不差。预测误差是另一列。没有从乱码表格里抄数字。

[abstract-only] [author claim] Guestrin、Krause 与 Singh，ICML 2005，DOI `10.1145/1102351.1102385`。摘要说最高熵是常见做法，互信息更好，并且最大化互信息是 NP-complete。全文下载失败，所以不描述正文方法。JMLR 2008 是读过全文的扩展版本。

## 2. 参数互信息也不是决策损失

[full-text read] [author claim] Mussmann 等，arXiv:2211.09283，preprint，`paper verify` 年 2022。BALD/EIG 最大化标签与参数的互信息，分类目标是期望测试误差。他们用后验样本推导对数损失和 0-1 损失的期望误差下降。设定是池式分类，被查询的标签会被观测到。arXiv HTML 含有未删除的草稿评论，评论不当成结果。

[full-text read] [author claim] Ao 与 Li，AAAI 2024，DOI `10.1609/aaai.v38i18.30012`。效用可以是后验精度、二次损失或 EIG。本文估计的是 EIG 对设计变量的梯度。

[full-text read] [author claim] Wu、Liang 与 Yang，arXiv:2604.21849，preprint。即使 EIG 能被估计，KL 效用仍对尾部、近零似然和罕见观测敏感。这是预印本引言，不把它写成噪声地图的既定结论。

[full-text read] [author claim] Alexanderian，Inverse Problems 2021，DOI `10.1088/1361-6420/abe10c`。设计的目的是降低参数不确定性，测量被假定执行。

## 3. 声场放置仍然假定传感器能放上去

[full-text read] [author claim] Nishida 等，IEEE TSP 2022，DOI `10.1109/tsp.2022.3156012`。均方误差和条件熵是两个目标。放置区域可以不同于估计区域。没有人的接受概率。

[full-text read] [author claim] Verburg 等，EURASIP 2024，DOI `10.1186/s13636-024-00364-4`。位置最小化参数或重建声压的 Bayesian Cramér-Rao bound。摘要中的大约 50% 测量减少是相对随机布置的作者概括，本项目没有复现。

## 4. 选格和选人优化的是别的奖励

[full-text read] [author claim] Wang 等，ICDCS 2018，DOI `10.1109/icdcs.2018.00164`，读 arXiv:1804.07047。同样推断质量保证下，感知格子最多减少 15%。这是作者主张。

[full-text read] [author claim] Li 等，ToN 2022，DOI `10.1109/tnet.2022.3169180`，读 arXiv:2107.01385 的第 1–2 节。目标是预算和容量下合格样本的期望收益。选择被假定产生观测。

[full-text read] [author claim] Simon 等，TCOM 2024，DOI `10.1109/tcomm.2024.3381718`，读 arXiv:2309.10594 的摘要。报价表示意愿。平均任务完成时间至少降低 16% 是作者主张，指标不是地图 MAE。

[full-text read] [author claim] Zhang 等，MBE 2023，DOI `10.3934/mbe.2023533`。结论的前提是用户轨迹已知。

[full-text read] [author claim] Huang 等，2026，DOI `10.1007/s42486-025-00202-2`。员工前往所选子区域。交通流准确率数字是分类任务上的作者主张。

## 5. 从这些全文走到本项目的解释

[our interpretation] 第 1–4 环支持的结构是：高不确定性、互信息、参数信息增益和地图或分类误差可以不是同一个目标；已读的放置论文把“测到了”当作默认；已读的分配论文把人的不确定放在能力、报价或“轨迹已知”上。把到达、接受、测量噪声、空间相关和成本放进同一次噪声地图误差期望，是下一步要定义的决策值，不是上述任何一篇的定理。

## 6. 本仓库已经观察到的，以及还没有的

[local experiment, not literature] `experiments/results/main/summary.json`，regular，5 个种子均值。`audit compare` 把同一预算的 uncertainty、min_cost、mupsa 标成 comparable，把不同预算标成 not directly comparable。

| 预算 | uncertainty | min_cost | mupsa |
| --- | --- | --- | --- |
| 16 | 6.397 | 6.224 | 5.854 |
| 24 | 6.852 | 4.939 | 6.232 |

数字四舍五入到三位小数。mupsa 的平均到达大约 0.93–0.96，写在 `innovation_analysis.md` 所依据的同一文件里。高到达和更低的 MAE 没有同时出现在每个预算上。

[not yet tested] 没有一行是“含五个因素的一步期望地图误差下降”。LinUCB 在 regular、预算 24、5 个种子上的平均因果 MAE 约 5.056，但训练奖励使用了仿真误差下降，`audit compare` 不把它和上表排在一起。

## 7. 排除项

DOI `10.21203/rs.3.rs-4954416/v2` 的题名以 WITHDRAWN 开头。它不进入证据链，只保留为“移动预测加分配曾经被写过并被撤回”的警告。
