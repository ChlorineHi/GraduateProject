# 负面结果与访问失败

这里记录检索失败、不能迁移的假设、以及本仓库里已经和“更完整就更好”相反的数字。失败不是论文结论。

## 检索与全文

Run `20261110-013339-joint-sampling-location-and-pa` 的状态是 partial。

- DBLP 第 1 次返回 HTTP 202 反爬页面，之后 3 次 `skipped_source`。没有再请求。
- Semantic Scholar 没有 `S2_API_KEY`，第 1 次 HTTP 429。这次 run 没有成功的 Semantic Scholar 结果。
- 没有 mailto、OpenAlex 邮箱或 Unpaywall 邮箱。Unpaywall 没有调用。没有编造邮箱或 key。
- Europe PMC 和 PubMed 没有调用。自动计划把 “cell selection” 配到生命科学，这个匹配被拒绝。

全文失败：

| 标识 | 发生了什么 | 因此采用的阅读深度 |
| --- | --- | --- |
| DOI `10.1145/1102351.1102385` | figshare 是 JavaScript 墙。CMU KiltHub 返回 anti-bot challenge。没有绕过。 | abstract-only |
| DOI `10.1109/mcom.2016.7509395` | OpenAlex 没有 OA PDF。HAL `hal-01346728` 有题名和 DOI，没有 `fileMain_s`。 | abstract-only |
| DOI `10.1109/ojcs.2022.3177290` | OpenAlex 记录的 IEEE PDF 链接 HTTP 404。 | abstract-only |
| DOI `10.1109/jiot.2020.3024833` | 标成 green OA 的地址是 UvA-DARE 简介页，解析约 64 行，摘要在半句处截断。 | abstract-only。只用页面上写完的句子 |
| DOI `10.1016/j.comnet.2019.06.010` | ScienceDirect HTTP 403。 | 后来读了 HAL 作者稿 `hal-02321018`，不是出版商 PDF |
| DOI `10.5555/1390681.1390689` | OpenAlex 当时没有给出 OA 地址。 | 改从 `https://jmlr.org/papers/volume9/krause08a/krause08a.pdf` 下载出版 PDF 后读了主要章节 |

解析限制：`pypdf` 7.0.0 没有版面模型。JMLR 公式出现乱码。IEEE 双栏有的 PDF 抽不出 methods 标题，所以 Access 2019 和 TCOM 2024 只把摘要里读到的句子当成 author claim。没有安装 fontTools 并不改变这个限制。没有对任何一篇跑 `paper confirm`。`graph coverage` 因此仍把阅读账本记成 metadata。文档里的 full-text read 指读过解析文本的指定章节，不是 sentinel 确认。

arXiv:2211.09283 的 HTML 把多段草稿拼在一起，里面有 “Steve:” 一类评论。那些评论不进入证据。

## 不能迁移

[hypothesis] `transfer check` 的记录：

- 期望误差下降：被查询标签会被观测到、任务是分类。这两条在本项目为 violated。这里没有分类标签，选中的人可能不接受。
- 高斯过程互信息：候选位置会被实际装上传感器。这条为 violated。失败条件“设计没有被执行”为 present。
- CAWS 的签名假设是上下文先被观测、奖励是 Bernoulli、选中工人产生观测。共享的必要假设列表是空的。

[our interpretation] 把机器人信息路径规划搬过来，会变成平台选择并改写轨迹。机会式规则不允许这样做。把分类 EER 搬过来，会假定查询一定得到标签。把 CAWS 的收益搬过来，优化的是样本合格而不是地图误差。

`compare methods` 的 structural similarity 不是正面证据，也不是负面证据。它只是检索分数。

## 本仓库里和“完整模型全面更好”相反的数

这些数来自 `experiments/results/main/summary.json`，是合成实验，不是论文。同一预算内的主方法由 `audit compare` 标成 comparable。跨预算不排名。

[local experiment] regular，5 个种子平均因果 MAE：

- 预算 8：不确定性 5.576，MU-PSA 7.520。不确定性更低。
- 预算 16：MU-PSA 5.854，是该预算六种主方法里最低的。这只在这个预算成立。
- 预算 24：最小成本 4.939，MU-PSA 6.232，不确定性 6.852。
- 预算 36：最小成本 5.147，MU-PSA 6.000。

MU-PSA 的平均到达大约 0.93–0.96。高到达没有在每个预算上对应更低的 MAE。

[local experiment] complex、预算 24、5 个种子的消融平均 MAE：完整 6.816，去掉移动 7.748，去掉不确定性 8.149，去掉覆盖 6.576，去掉重规划 6.319。去掉覆盖或重规划略好。不能写“每一项都有贡献”。

[local experiment] LinUCB 在 regular、预算 24、5 个种子上的平均因果 MAE 约 5.056。训练奖励含仿真误差下降，所以 `audit compare` 不把它和上面的 5 种子主方法排成一张榜。12 次训练回报没有单调上升。

## 明确不采用的条目

DOI `10.21203/rs.3.rs-4954416/v2`，题名 *WITHDRAWN: A Multi-Task Allocation Framework...*。`screen decide` 将其 exclude，原因是 withdrawn。它不作为可迁移方法，也不作为本项目创新性的证据。它只说明“用移动预测做任务分配”曾经被写过，而且该稿被撤回。

## 还没有的负面或正面结果

[not yet tested] 一步期望地图误差下降还没有实现，因此还没有“它比不确定性更好”或“它比不确定性更差”的实验。H1–H3 的否定条件写在 `algorithm_hypotheses.md`。在那个计算做出来之前，不能把假设写成发现。
