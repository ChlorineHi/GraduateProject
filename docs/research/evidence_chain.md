# 证据链

1. Verified Fact：公平协议的环境种子不含方法名和预算。测试 `test_shared_environment_hash_across_methods` 检查两个方法的 `environment_hash` 相同、`algorithm_seed` 不同，并且噪声场和轨迹数组没有被回合改写。
2. Verified Fact：`eer_reach` 的值和 `src/urbannoise/predictors.py` 里的 `expected_error_reduction` 一致，评分在 `assignment.py`。
3. Author Claim，且只限于摘录深度：arXiv:2211.09283 的实验节摘录比较的是分类主动学习，不是噪声地图。不能把那篇的胜负移到本仓库。
4. Agent Interpretation：Krause 等 2008 的互信息假设传感器会被放下去。本系统的人可能拒绝，所以互信息不是这里的实现。
5. Verified Fact：数值结论只来自 `experiments/results/phase2/fair_main/summary.json` 和 `experiments/results/phase2/real_runs.json`。旧目录 `experiments/results/main` 是另一套协议，不能和这些数字比高低。
6. Unsupported：没有证据说 `eer_reach` 在所有预算、所有真实子集上都降低了误差。负结果写在 `negative_results.md`。
