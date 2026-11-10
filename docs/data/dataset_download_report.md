# 数据集下载报告

清单生成时间：2026-11-10T01:37:49+00:00。数据目录：/workspace/data。
下面每一行都来自 `data/manifests/download_manifest.json`，并在这次校验中重新核对了磁盘字节数。sha256 是下载脚本在写完文件后计算的，这次校验没有重算哈希。
失败次数：0

| 文件 | 状态 | 字节 | sha256 | 错误 |
| --- | --- | --- | --- | --- |
| POI_datacategories.csv | downloaded | 1151 | 93296e7594070c3198e6f06a16b4942344fe2899fec27c363b0e5e00b8e14f89 | None |
| cell_POIcat.csv.gz | downloaded | 626648 | 8d6a284896a95e49ebafddc06f583a4f61cd66ccb089cf985f3ec589bf348533 | None |
| Geolife Trajectories 1.3.zip | downloaded | 313164406 | 1107c5ac064d0a23c8d021a8736a77e53abc75b227062e6260342c6a8d86bdb6 | None |
| Germany.zip | downloaded | 193453494 | 2d276a995ee6bda7148435996f7dc20c58123b6b2d1f997c05374b6a6a4ed1eb | None |
| France.zip | downloaded | 876517026 | 910a9343bf15a1f9e53b0d8f880a79c6c70aab1676fae4edb56daea5cd1a3f24 | None |
| Spain.zip | downloaded | 69283635 | a58616a66e6c109db6068e74620193e9b05b0b164b363f7cce3f428420a84476 | None |
| Italy.zip | downloaded | 31402272 | a583f61ac498ebc619709c29212f875be31db82c795e22aad90b1bd697449cc9 | None |
| Belgium.zip | downloaded | 37893139 | bfa1f2d69a05361614e16d58af3412dd8ec9444d07f40d54ca6de0558e6ec53a | None |
| Netherlands.zip | downloaded | 48857644 | 4be34d640e235f23f97f93e63fa0bd57d458e051342766c4c4587f3f0aae5564 | None |
| Switzerland.zip | downloaded | 77771147 | e71c5c338e78ef051e4bd42eb4a6710eeed6d416adce88b677d47d83632bbbdd | None |
| Austria.zip | downloaded | 47364294 | a93e975557743e33f37413464755848a858dc317f50695016c1b1889fcc7f74e | None |
| Portugal.zip | downloaded | 8581877 | 7b6c41add059d07a297105496a4b9ce590f1f4e3cb969f6c2091ba5499cf04a2 | None |
| Luxembourg.zip | downloaded | 1404650 | be6e2608fe4b25dcabfce668f627a41980326224baa7c3f38d3e0fc410ed5821 | None |
| China.zip | downloaded | 19100109 | 084b599fdf21039aad28c8dcd44a5dac4f7bbf38667d8a3b12fc8cb930d875a7 | None |
| United Kingdom.zip | downloaded | 157973023 | 9153e514cf7ee7173785c49111a6162a0128089be497c414ed5c32b09b45d50b | None |
| Japan.zip | downloaded | 5598110 | 7e6fe54f973efbf934a365bf7740fdb89b70a089cfc32df3a817812ea2ea4f85 | None |
| Brazil.zip | downloaded | 45844212 | 540aef978fd95a0fcb9e09a2a59bf91ba0ee98b2a85d771f3d7f6580181df9aa | None |
| Canada.zip | downloaded | 118737661 | 4eb533c8fb39545d404616faea70dc28bf1124b1e925f03b1ef2ab8b0e804592 | None |
| Australia.zip | downloaded | 78260891 | 7b0ef54f4a0803a32d8d42cc23a56b3102623b52b1d2b651ac3740f8ad3a7f70 | None |
| yjmob100k-dataset2.csv.gz | downloaded | 111175823 | f477b3defb9511f8d326d7673eb1f436e36c7a136e49688557fcfabfcb28bb4e | None |
| yjmob100k-dataset1.csv.gz | downloaded | 419026821 | fdf3d6bc8415debdca5fae1d9184a8e41743ca43528e2b7b050f114cb65b9551 | None |

YJMob100K 的四个文件来自 Zenodo record 10836269，许可证字段为 cc-by-4.0。
GeoLife 的 zip 来自 Microsoft 下载页 `https://www.microsoft.com/en-us/download/details.aspx?id=52367` 里的 `downloadFile.url`。
NoiseCapture 的 zip 使用 `https://data.noise-planet.org/dump/{Country}.zip`。HTTP 而不是 HTTPS 的同名地址会返回网页而不是 zip，因此下载脚本使用 HTTPS。
这次清单里没有失败项。`noisecapture_exploit.html` 没有出现在清单中，因为官方数据页指向的是国家 zip，而不是一份可下载的 exploit 归档。
