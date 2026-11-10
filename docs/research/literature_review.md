# 文献调研记录

## 检索过程

CDRI 安装在 `.cursor/skills/cdri`。`config check` 的结果是：没有 mailto、OpenAlex 邮箱、Semantic Scholar key 或 Unpaywall 邮箱，也没有 PDF 解析库。因此没有做全文抓取，也没有把摘要写成“已精读方法”。

实际运行：

- `20261109-155517-sparse-mobile-crowdsensing-tas`：较早的一次检索，原始记录较少。
- `20261109-161733-sparse-mobile-crowdsensing-tas`：`landscape plan` 加 `landscape run`。OpenAlex 3 次成功，Crossref 2 次成功，arXiv 3 次空结果。去重后 38 条。失败列表为空。出版状态由 CLI 标成 published 32、preprint 5、unknown 1。

另外用 Crossref 或 OpenAlex 单独核实了数据集论文和若干经典工作的题名、年份和作者。这些核实与 landscape 运行是分开的。

阅读深度（只描述 2026-11-09 这一轮）：

- **已核实元数据**：题名、年份、 venue、DOI 或 OpenAlex 记录与下面列出的条目一致。
- **摘要级**：CDRI 记录里带有摘要，下文只转述问题，不把摘要中的实验数字写成已复核结果。
- **未读全文**：2026-11-09 这一轮没有一篇论文完成 CDRI 的 `paper read` / `paper confirm`。因此这一节不写“方法节已核对”。2026-11-10 的第二轮拿到了部分全文，那些论文的阅读深度以下一节为准，不改这里已经核对过的题名和 DOI。

## 问题背景

移动群智感知把携带传感器的人和设备当成可移动的采集节点。Ganti、Ye 与 Lei 在 2011 年把这一范式的状态和挑战写成综述，DOI `10.1109/MCOM.2011.6069707`。Capponi 等人 2019 年的 COMST 综述（DOI `10.1109/COMST.2019.2914030`）从摘要看，强调手机传感器、人的移动带来的覆盖，以及参与者因为隐私而不愿共享数据。这是作者在摘要中的主张，不是本项目的实验结果。

稀疏群智感知进一步承认预算不够覆盖全部区域。Wang 等人 2016 年在 IEEE Communications Magazine 的文章题为 *Sparse mobile crowdsensing: challenges and opportunities*（DOI `10.1109/MCOM.2016.7509395`）。Zhao 等人 2022 年的综述（DOI `10.1109/OJCS.2022.3177290`）在摘要中把稀疏群智感知描述为：只感知一小部分子区域，并利用时空相关推断未采样区域。摘要同时点名两个困难：感知单元选择和缺失数据推断。

噪声地图是群智感知的一个具体对象。Picaut 等人 2019 年发表于 *Building and Environment* 的论文题名是 *An open-science crowdsourcing approach for producing community noise maps using smartphones*（DOI `10.1016/j.buildenv.2018.10.049`）。本次只核实了题名和作者，没有阅读测量协议全文，因此不把不同分贝指标当成可以混用的同一物理量。代码里的导入器按字段名保留 `laeq`、`leq`、`noise_level` 等指标。

## 人会去哪里

Song、Qu、Blumm 与 Barabási 2010 年在 *Science* 讨论人类移动的可预测性上限（DOI `10.1126/science.1177170`）。题名和作者已由 Crossref 核实。本文不引用“93%”这一常被转述的数字，因为本次没有复核正文计算，也没有复核后续对熵估计偏差的讨论。项目里的移动模型只是时段频率和马尔可夫转移的混合，并用 Top-1、Top-3、NLL 和 Brier 分数在仿真轨迹上评估。

YJMob100K 的数据论文已核实：Yabe 等人，*Scientific Data*，2024，DOI `10.1038/s41597-024-03237-9`。完整数据包没有下载。适配器按列名读取 `uid`、`day`、`timeslot`、`x`、`y`，坐标系统写成 `yjmob_virtual_500m`。虚拟网格不会被标成北京或东京。

GeoLife 的官方下载页是 Microsoft Download Center `id=52367`。Zheng、Zhang、Xie 与 Ma 2009 年 WWW 论文 *Mining interesting locations and travel sequences from GPS trajectories*（DOI `10.1145/1526709.1526816`）已由 OpenAlex 核实。适配器读取 `.plt`：跳过 6 行表头，保留 WGS84 经纬度。完整轨迹集没有下载，所以本报告不声称重新统计了用户数或轨迹条数。

## 任务该分给谁

Guo 等人 2019 年的综述（DOI `10.1109/ACCESS.2019.2896226`）从摘要看，把无线传感器网络和群智感知的任务分配放在数据质量与感知成本两个目标下比较。摘要级信息只说明“质量和成本是共同议题”，不能推出某一种算法在本项目数据上更优。

ISIATasker（DOI `10.1109/JIOT.2021.3095160`，Crossref 给出的出版年是 2022）在摘要中定义 instant-sensing then instant-actuation：有些任务在被发现时就要执行，而不能先发布再等待。这和本项目“先有观测，再预测下一时间片，再分配”不是同一个问题。可迁移的只是“时间紧”这一点。负迁移风险是：如果把紧急触发模型直接套到周期性噪声场上，会忽略已经存在的空间基线。

2022 年 *Sensors* 上的个性化成本分配（DOI `10.3390/s22072751`）在摘要中批评静态排序，认为上一个任务会改变用户完成下一个任务的起点，用户偏好也会改变实际成本。本项目的仿真每次只给一名参与者分配一个目标时间片的任务，没有建模连续行程的路径成本。因此不能说已经实现了他们的动态组合优化。

2024 年 *Mathematics* 上的任务重要性分配（DOI `10.3390/math12162471`）在摘要中用任务队列、任务重要性和参与者能力。本项目的价值函数是不确定性、覆盖缺口、时间缺口和重复惩罚的加权和，不是他们的队列稳定性目标。

Wu 等人关于细粒度用户画像的 TMC 论文（DOI `10.1109/TMC.2020.2993963`，Crossref 出版年 2021）在摘要中主张同时用偏好和可靠性做推荐，而不是只由平台集中指派。本项目把接受概率、设备质量和到达概率分开，但接受概率是仿真参数，不是从真实拒绝记录学出来的。

2023 年动态任务分配框架（DOI `10.1155/2023/7093792`）的摘要说：先把单个工人建模成马尔可夫决策过程，用 DDQN 在历史任务上离线学习，再做在线分配。本项目没有训练 DDQN。LinUCB 只在最多 20 个候选配对的 10 维上下文上更新。两者都承认分配是序贯的，但算法和动作空间不同。

2021 年半机会式深度学习分配（DOI `10.1155/2021/6643229`）的摘要强调参与者资源瓶颈和系统效用需要同时考虑。本项目用预算和每人每时间片一个任务来表达资源瓶颈，没有使用他们的深度模型。

*Wireless Networks* 2023 年的时空特征分配（DOI `10.1007/s11276-022-03138-y`）只核实了题名、年份和 DOI。CDRI 记录中的摘要字段为空，所以这里不描述它的方法。

Restuccia 等人 2017 年的 QoI 综述（DOI `10.1145/3139256`）从摘要看讨论人作为主要感知者时的信息质量。本项目用 `quality` 和测量裁剪标志区分数据，没有实现他们的完整质量分类法。

## 哪里值得采样

Krause、Singh 与 Guestrin 2008 年 JMLR 论文（DOI `10.5555/1390681.1390689`）以及 Guestrin、Krause 与 Singh 2005 年 ICML 论文（DOI `10.1145/1102351.1102385`）研究高斯过程下的传感器放置。2008 年论文的题名包含次优保证和经验研究。2026-11-09 只使用了题名。2026-11-10 读了 JMLR 的出版 PDF，见下一节；ICML 2005 的全文仍然没有拿到。本项目的 IDW 不确定性不是高斯过程的后验方差，价值函数也不是互信息。因此不声称继承了 (1−1/e) 的子模保证。固定核高斯过程只作为噪声预测的一个对照，而且在样本数不在 8 到 220 之间时会退回 IDW。

## 本次检索里明确不采用的条目

2024 年一条题为 *WITHDRAWN: A Multi-Task Allocation Framework...* 的预印本出现在检索结果中（DOI `10.21203/rs.3.rs-4954416/v2`）。题名已标明撤稿。它不被当作可迁移方法。它只说明“用移动预测做任务分配”这一说法已经有人写过，而且该稿被撤回，不能拿来支持本项目的创新性。

若干 2025–2026 年的预印本或刚出版条目只保留在检索日志里，没有进入方法设计。原因是没有全文，也没有时间逐篇核对。

## 和本项目的关系

文献支持三件已经存在的事：人会移动，预算下不能全测，未测区域需要推断。文献没有授权本项目把“到达概率 × 接受概率 × 质量 × 启发式价值 − 成本”称为新的理论保证。这个式子是工程上的候选策略，名字 MU-PSA 只在系统内部使用。实验一章报告它在哪些预算下误差更低，在哪些预算下不如最小成本匹配或只按不确定性采样。

## 2026-11-10 第二轮：不确定位置下的选点和派人

这一轮只回答一个问题：在未来位置不确定、观测稀疏、预算有限时，怎样同时决定在哪里采样、把任务交给谁，才会让噪声地图误差下降。高预测不确定性本身是不是期望地图误差的下降，是单独检查的一点。

### 检索实际跑了什么

CDRI 项目目录是这个 worktree。`config check` 仍然没有 mailto、OpenAlex 邮箱、Unpaywall 邮箱、Semantic Scholar key。本机后来安装了 `pypdf` 7.0.0，只用于解析已经合法下载的 PDF。没有编造 API key。

自动 `landscape plan` 把 “cell selection” 里的 cell 配到了生命科学，并把 home source 指到 Europe PMC 和 PubMed。这个匹配被拒绝：这里的 cell 是感知单元。自动的 distant 查询用了本体里的 “hierarchical Bayesian model”“empirical Bayes shrinkage”“conformal prediction”“controllability network”。这些词没有对准“期望地图误差”。计划文件因此改写了 distant 和 contradictory 查询，机制仍是 `bayesian-inference`、`uncertainty-quantification`、`control-theory`。Europe PMC 和 PubMed 没有再请求。时间窗由 CLI 按 2026-11-10 计算：core 从 2021-11-10 起，foundational 查询没有日期下限。

实际运行 `landscape run --plan`，run id 是 `20261110-013339-joint-sampling-location-and-pa`。状态是 partial。去重后 537 条。出版状态由 CLI 标成 published 372、preprint 147、unknown 17、accepted 1。

| 来源 | 结果 |
| --- | --- |
| OpenAlex | 15 次 ok |
| Crossref | 13 次 ok |
| arXiv | 4 次 ok，10 次 empty |
| DBLP | 第 1 次 HTTP 202 反爬页面，之后 3 次 `skipped_source`，没有再请求 |
| Semantic Scholar | 没有 `S2_API_KEY`，第 1 次 HTTP 429，该源在这次 run 里没有成功结果 |

`graph coverage` 在签名写入之后报告：知识库里这篇联合问题还没有一个已登记的求解方法；阅读账本深度仍是 metadata，因为没有跑 `paper confirm`。下面的 “full-text read” 是对解析文本的阅读，不是 sentinel 确认。

`learn_history` 取 auto。只读了 `experiments/results/main/summary.json` 和 `docs/algorithms/mupsa.md`。没有重跑实验，也没有反序列化 checkpoint。这些数字是本仓库合成实验，不是论文结果。

### 全文拿到了，以及没拿到

合法级联是 arXiv HTML/PDF、Europe PMC、OpenAlex 记录的 OA 地址。Unpaywall 因没有邮箱而跳过。另外两份是公开来源上的文件，再用 `paper fetch --file` 解析：JMLR 出版 PDF `https://jmlr.org/papers/volume9/krause08a/krause08a.pdf`；Computer Networks 2019 的 HAL 作者稿 `https://hal.science/hal-02321018/document`。

失败：

- `10.1145/1102351.1102385`：OpenAlex 的 figshare 页是 JavaScript 墙。CMU KiltHub 返回 anti-bot challenge。停在摘要。
- `10.1109/mcom.2016.7509395`：OpenAlex 没有 OA PDF。HAL `hal-01346728` 有题名和 DOI，没有 `fileMain_s`。停在这一轮检索带回的摘要。
- `10.1109/ojcs.2022.3177290`：OpenAlex 的 IEEE PDF 链接返回 404。停在摘要。
- `10.1016/j.comnet.2019.06.010` 的 ScienceDirect 链接 HTTP 403。后来改用 HAL 稿，见下表。
- `10.1109/jiot.2020.3024833`：OpenAlex 标成 green OA，但 “PDF” 地址实际是 UvA-DARE 简介页。解析结果 64 行，不是论文正文。只采用页面上写完的摘要句，不用被截断的半句。

下表的阅读深度：

| 论文 | DOI 或 arXiv | 状态 | 阅读深度 |
| --- | --- | --- | --- |
| Krause, Singh, Guestrin, JMLR | 10.5555/1390681.1390689 | published, 2008 | full-text read（JMLR 出版 PDF：引言、熵与互信息、贪心规则、结论） |
| Singh, Krause, Guestrin, Kaiser, JAIR | 10.1613/jair.2674 | published, 2009 | full-text read（第 1–2 节问题定义；实验曲线上的数字没有摘录） |
| Cao, Low, Dolan, AAMAS | 10.65109/frmm7982 | published, 2013；读的是 OpenAlex 指向的 arXiv PDF 1302.0723 | full-text read（熵路径、互信息路径，以及实验里分开的 entropy / mutual information / prediction error） |
| Mussmann 等 | arXiv:2211.09283 | preprint | full-text read（arXiv HTML 的问题设定和第 6 节方法）。HTML 里还有带评论的草稿重复段，那些评论不当成结果 |
| Li, Zhao, Yu, Cheng, Lv, ToN | 10.1109/tnet.2022.3169180 | published, 2022；读的是 arXiv:2107.01385 PDF | full-text read（第 1–2 节模型和目标） |
| Wang 等, ICDCS / arXiv:1804.07047 | 10.1109/icdcs.2018.00164 | published, 2018 | full-text read（arXiv PDF 的引言和摘要中的主张；Q 网络公式没有逐式核对） |
| Liu 等, Computer Networks | 10.1016/j.comnet.2019.06.010 | published, 2019 | full-text read（HAL 作者稿的结论；这不是出版商 PDF） |
| Huang 等, MBBALD | 10.1007/s42486-025-00202-2 | published, 2026 | full-text read（摘要、引言中的问题、第 4.1 节框架） |
| Zhang 等, Mathematical Biosciences and Engineering | 10.3934/mbe.2023533 | published, 2023 | full-text read（摘要与第 6 节结论；STGCN 公式没有逐式核对） |
| Nishida, Ueno, Koyama, Saruwatari, IEEE TSP | 10.1109/tsp.2022.3156012 | published, 2022 | full-text read（PDF 第 1 页摘要和问题陈述） |
| Verburg, Elvander, van Waterschoot, Fernández-Grande | 10.1186/s13636-024-00364-4 | published, 2024 | full-text read（摘要、引言、重建问题的开头） |
| Simon, Ortiz, Saad, Klein, IEEE TCOM | 10.1109/tcomm.2024.3381718 | published, 2024；读的是 arXiv:2309.10594 PDF | full-text read（摘要：意愿、报价、努力未知） |
| Liu 等, IEEE Access | 10.1109/access.2019.2924184 | published, 2019 | full-text read（PDF 摘要：多任务格子与推断） |
| Alexanderian, Inverse Problems | 10.1088/1361-6420/abe10c | published, 2021；读的是 arXiv:2005.12998 PDF | full-text read（第 1 节：设计用来降低参数不确定性） |
| Ao, Li, AAAI | 10.1609/aaai.v38i18.30012 | published, 2024 | full-text read（摘要和引言：效用可以是 A/D、二次损失或 EIG；本文做的是 EIG 梯度） |
| Wu, Liang, Yang | arXiv:2604.21849 | preprint | full-text read（第 1 节：EIG 的 KL 形式有它自己的失败方式） |
| Guestrin, Krause, Singh, ICML | 10.1145/1102351.1102385 | published, 2005 | abstract-only |
| Wang 等, Communications Magazine | 10.1109/mcom.2016.7509395 | published, 2016 | abstract-only（这一轮摘要；全文失败） |
| Zhao 等, IEEE Open Journal of the Computer Society | 10.1109/ojcs.2022.3177290 | published, 2022 | abstract-only（PDF 404） |
| Zhu 等, IEEE Internet of Things Journal | 10.1109/jiot.2020.3024833 | published, Crossref 年 2021 | abstract-only（仓库简介页，不是正文） |

### 不确定性不是期望地图误差

[full-text read] [author claim] Krause、Singh 与 Guestrin 在 JMLR 2008 写明：把传感器放在高斯过程熵（方差）最高的地方，是一个间接准则。对固定核，条件方差不依赖于已经观测到的数值，所以开环设计和用到新观测的闭环设计没有差别。熵准则会把点放到区域边界，因为被选中的传感器彼此最不确定。互信息改成最大化已选位置和未选位置之间的信息，贪心增量是 `H(y|A) - H(y|未选)`，第二项把点拉向还没被解释的区域。精确最大化互信息是 NP-complete。在离散足够细时，贪心有 `(1-1/e)` 量级的近似，近似的是互信息，不是地图的绝对误差。结论里作者写，他们的实验里互信息在预测精度上常常好于熵以及 A/D/E 最优设计。这是作者对那两份温度等数据的主张。他们也讨论了节点失效下的稳健放置，默认情形仍是传感器会被装上。

[abstract-only] [author claim] ICML 2005 的摘要已经说：常见做法是放在熵最高的点，他们提出互信息并认为它更好，而且最大化互信息是 NP-complete。摘要里的 “better placements” 没有在正文里复核。

[full-text read] [author claim] Cao、Low 与 Dolan 把熵和互信息都做成多机器人路径规划，并在实验里分开报告 entropy、mutual information 和 prediction error。熵算法在熵指标上更好或至少不差，互信息算法在互信息指标上更好或至少不差。预测误差是第三个指标。因此“在某个信息指标上更优”不能写成“地图误差一定更低”。路径是规划器选出来的，机器人被假定会沿这条路径走。

[full-text read] [author claim] Singh、Krause、Guestrin 与 Kaiser 在 JAIR 2009 用互信息给机器人路径打分，约束是每台机器人的行驶和测量成本，例如电池。路径是被选中的访问序列，不是对一个人未来轨迹的预测。

[full-text read] [author claim] Mussmann 等人的预印本把 Expected Information Gain / BALD 和 Expected Error Reduction 分开：BALD 最大化标签和参数的互信息，分类的目标却是降低测试误差。他们的分数是验证集上期望损失的下降，并且假定被查询的标签会被观测到。任务是图像分类，不是空间场。arXiv HTML 含有未删除的草稿评论，评论不进入证据。

[full-text read] [author claim] Alexanderian 的综述把实验设计定义成：用有限测量降低 PDE 反问题里参数的不确定性。A-最优是参数的平均方差。设计变量是测量位置，测量被假定会执行。

[full-text read] [author claim] Ao 与 Li 列出多种效用：后验精度、二次损失、EIG。他们优化的是 EIG 对设计变量的梯度，不是一张噪声地图的绝对误差，也没有随机拒绝。

[full-text read] [author claim] Wu、Liang 与 Yang 的预印本写：即使 EIG 能被估计出来，KL 效用仍然对尾部、近零似然和罕见观测敏感。所以“换成 EIG”本身也不是地图误差。该文是预印本。

[full-text read] [author claim] Nishida 等人允许放置区域和要估计的声场区域不一样，并用均方误差或条件熵做两个不同的目标。放置位置来自候选区域，不是一个可能不去的人。

[full-text read] [author claim] Verburg 等人最小化 Bayesian Cramér-Rao bound，对象可以是声场参数，也可以是感兴趣区域上重建的声压。摘要报告：相对随机布置，为重建而优化的位置大约把测量数量减少 50%。这是作者对数值实验和房间脉冲响应实验的概括，本项目没有重做。传感器由实验者放置。

### 选格和派人仍然经常被分开

[full-text read] [author claim] Wang 等人的 DR-Cell 选择格子，使推断误差低于阈值所需的采样格子变少。摘要中的作者主张是：在同样的推断质量保证下，感知格子最多减少 15%。引言把参与者写成被招募来采集已选格子的人。读过的部分没有把“到达概率 × 接受概率”写进地图误差的期望。

[full-text read] [author claim] Computer Networks 2019 的 HAL 稿用 Q-learning 和带 LSTM 的 DQN 做格子选择，结论说实验显示采集成本下降，并把“完全在线、不再需要预先采集训练数据”留作未来工作。稿件没有把人的未来轨迹改写成任务路径。

[full-text read] [author claim] IEEE Access 2019 同时做多任务压缩感知推断和 `<cell, task>` 的强化学习选择，利用任务内部和任务之间的相关。决策单位是格子和任务类型，不是一个可能拒绝的具体的人。

[full-text read] [author claim] MBBALD 批评稀疏群智感知只用覆盖或补全价值，而下游任务需要的是对决策有用的子区域集合。框架里，员工前往被选位置、采集、再由专家标注，分类器是下游任务。作者在摘要中报告：缺失率超过 60% 后 MBBALD 开始优于其他算法；交通流数据在 50% 缺失时比第二名高 4% 以上的准确率。这些百分比是作者对三个真实数据集分类准确率的主张，不是噪声地图的 MAE，也没有拒绝概率。作者还写 BatchBALD 的限制：它看的是模型被排除的速度，而且原方法假定样本更独立，而感知子区域是相关的。

[full-text read] [author claim] Zhang 等人用 STGCN-GRU 预测轨迹，再用 ADQN 在成本预算内招募用户。结论写的前提是 “provided that the user trajectory is known”：在轨迹已知时，为多个连续周期选择高贡献用户。作者把未来工作放在语义轨迹，没有声称平台可以改写这个人本来要走的路。把预测轨迹当成已知轨迹，和“只使用到达概率、不改未来轨迹”不是同一个假设。[our interpretation]

[abstract-only] [author claim] Zhu 等人的仓库摘要批评“每个样本成本相同”。他们的三步是信息建模、成本估计、成本–质量格子选择，策略名叫 Pareto Optimization Selection 和 Generalized Cost-Benefit Greedy。摘要点名 Parking、Flow、Traffic、Humidity 和三种成本地图。正文没有读到，所以不描述算法步骤之外的实验数字。Crossref 出版年是 2021。

[full-text read] [author claim] Li 等人的 CAWS 在预算和每人容量约束下，从大量能力未知的工人里选择。奖励是样本是否合格的 Bernoulli 变量，目标是期望累计收益，不是空间场的重建误差。上下文相似的工人被假定能力相似。作者强调预算小到不够把每个工人探索一次。选择被假定会产生一次观测。

[full-text read] [author claim] Simon 等人让移动单元用报价表示愿意参加，平台再分配。不确定的是努力和偏好。摘要中的作者主张包括：平均任务完成时间至少降低 16%。这不是噪声地图 MAE。报价是一次显式的接受信号；本项目的数据没有这种标签。

### 对本项目意味着什么

[our interpretation] 上面的全文支持一个结构，而不是一个可以抄的算法：信息指标、参数不确定性和预测误差可以被分开测量；传感器放置论文把“测到了”当作设计已经执行；工人选择论文把“人不确定”放在样本质量或是否接单上，奖励通常不是地图误差。把这两边乘在一起，还要乘上测量噪声和空间相关，才是噪声地图上的期望误差下降。

[hypothesis] [not yet tested] 高预测不确定性不等于这个期望。MU-PSA 的乘积启发式也不是这个期望，不能写成已发表的新方法。撤回预印本 `10.21203/rs.3.rs-4954416/v2` 仍然只说明“用移动预测做分配”曾经被写过并被撤回，不能用来证明本项目的创新。

接受概率在没有接受/拒绝标签的数据上只能仿真。[hypothesis] 机会式分配可以使用到达概率，但不能把这个人的未来轨迹改写成经过任务格。Zhang 等人的结论把“轨迹已知”当作招募的前提，正好标出这个不能照搬的假设。
