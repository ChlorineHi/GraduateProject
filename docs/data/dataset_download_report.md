# Dataset download report

Generated at 2026-11-10T01:45:57.404931+00:00 by `scripts/download_datasets.py`.

Counts, byte sizes, and hashes in this file are copied from `data/manifests/download_manifest.json`. They are the values measured for this run, not figures taken from papers.

Command: `scripts/download_datasets.py --dataset all --data-dir data --resume --workers 4`

## Status counts

- downloaded: 230
- failed: 1
- skipped_existing: 2

## Failures

### noisecapture / http-dump-index

- URL: `http://data.noise-planet.org/dump/`
- Status: `failed`
- Error: `HTTP 200 from http://data.noise-planet.org/dump/ returned no .zip links. title='Metabase' content_type='text/html; charset=UTF-8' server='Jetty(9.2.z-SNAPSHOT)' excerpt='<!DOCTYPE html>\n<html lang="en">\n    <head>\n        <meta charset="utf-8" />\n        <meta http-equiv="X-UA-Compatible" content="IE=edge" />\n        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, minimal-ui" />\n        <meta name="apple-mobile-web-app-capable" content="yes" />\n        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />\n\n        \n\n        <title>Metabase</title>\n\n        <base href="/" />\n\n     '`

## Files

| dataset | filename | bytes | md5 | sha256 | status | elapsed_s |
| --- | --- | ---: | --- | --- | --- | ---: |
| yjmob100k | yjmob100k-dataset1.csv.gz | 419026821 | `3781f6f03a118b5f639bdb4f94dcfdb8` | `fdf3d6bc8415debdca5fae1d9184a8e41743ca43528e2b7b050f114cb65b9551` | downloaded | 313.274 |
| yjmob100k | yjmob100k-dataset2.csv.gz | 111175823 | `ec769fafa7a746caa3d48d2844b9735c` | `f477b3defb9511f8d326d7673eb1f436e36c7a136e49688557fcfabfcb28bb4e` | downloaded | 30.205 |
| yjmob100k | cell_POIcat.csv.gz | 626648 | `93af4bb0b417cd20e95fdc1d8f7b459f` | `8d6a284896a95e49ebafddc06f583a4f61cd66ccb089cf985f3ec589bf348533` | downloaded | 3.525 |
| yjmob100k | POI_datacategories.csv | 1151 | `fd024e10c1d1dd91356d010413ace390` | `93296e7594070c3198e6f06a16b4942344fe2899fec27c363b0e5e00b8e14f89` | skipped_existing | 0.449 |
| geolife | Geolife Trajectories 1.3.zip | 313164406 | `8ed344eeb6ffccc30da112d824f3fe21` | `1107c5ac064d0a23c8d021a8736a77e53abc75b227062e6260342c6a8d86bdb6` | downloaded | 4.531 |
| noisecapture | http-dump-index |  | `` | `` | failed |  |
| noisecapture | Slovenia.zip | 209642843 | `0a80bf616f9e914dbfb6d71cca769663` | `70fdc702e99ff03efaf040a8bdcd6371d8803b1b308e76f54b497cc8a4e55310` | downloaded | 20.883 |
| noisecapture | Greece.zip | 284779450 | `6dba4c707490e0e5a5309fd9dbe57cf7` | `62fec8fa71e7d406d8fb50a03b1c5c56b5865a839a6cf916279efbe7bbf47e7e` | downloaded | 22.793 |
| noisecapture | Germany.zip | 193453494 | `80a450f4b8d5a014020853d0f90980ea` | `2d276a995ee6bda7148435996f7dc20c58123b6b2d1f997c05374b6a6a4ed1eb` | downloaded | 13.174 |
| noisecapture | United Kingdom.zip | 157973023 | `5b0f80b813a97e69269bf0e4db7421ed` | `9153e514cf7ee7173785c49111a6162a0128089be497c414ed5c32b09b45d50b` | downloaded | 17.11 |
| noisecapture | Canada.zip | 118737661 | `6b1ea97c666571da5c9885c58e4f0a34` | `4eb533c8fb39545d404616faea70dc28bf1124b1e925f03b1ef2ab8b0e804592` | downloaded | 11.571 |
| noisecapture | Croatia.zip | 87174783 | `6fe3b432c0ac814ae03a82eda19ce1d4` | `87e9c15a3f28cb94911f7421d02e580e75201f31a59a5936c66d0447fa76bc72` | downloaded | 6.651 |
| noisecapture | Australia.zip | 78260891 | `fa48bc67c770d2fb52f57a55eacc694c` | `7b0ef54f4a0803a32d8d42cc23a56b3102623b52b1d2b651ac3740f8ad3a7f70` | downloaded | 6.785 |
| noisecapture | Switzerland.zip | 77771147 | `fc9f3f571d7e73cb6700c8c743a58809` | `e71c5c338e78ef051e4bd42eb4a6710eeed6d416adce88b677d47d83632bbbdd` | downloaded | 7.799 |
| noisecapture | Norway.zip | 74293544 | `c56243a714a9484de414909939cf836d` | `5b246ba281599f38c95a541af18ad84f0cfc93b5a25f5fc1595b6615ddd0f0f9` | downloaded | 6.037 |
| noisecapture | France.zip | 876517026 | `1fbbe545a3ae5f0111a6c1f9d9e6a575` | `910a9343bf15a1f9e53b0d8f880a79c6c70aab1676fae4edb56daea5cd1a3f24` | downloaded | 59.597 |
| noisecapture | Poland.zip | 71359502 | `5ee9c33ac162bc520d7da5f240c6af02` | `0d944b82b7807f844733e45453ee656e5933bb38bd2ed2113251efc570b0376a` | downloaded | 5.9 |
| noisecapture | Spain.zip | 69283635 | `856903e4d470f399d84c5595ad3cb157` | `a58616a66e6c109db6068e74620193e9b05b0b164b363f7cce3f428420a84476` | downloaded | 5.747 |
| noisecapture | Ecuador.zip | 65812616 | `6325c67b64f3448c5561b973557ae339` | `2174d0d79f71246a620220cef8621c1950bb407b6d3672c15e9657502ae92c32` | downloaded | 5.434 |
| noisecapture | Malaysia.zip | 56475451 | `ef56615ce810e52c70285d7034077ffd` | `27936bb2adf5c5747e7ecb533d664a6f542355c22e169319bfadb00c9beab6c2` | downloaded | 5.152 |
| noisecapture | India.zip | 65241436 | `bd07c1978d46ff154d4461e912ec41b5` | `f7a2c206eca4d6ffdfc0524a5f7a54d99961601ad9b7bcd7097dce0c8120f293` | downloaded | 5.447 |
| noisecapture | Mexico.zip | 65506987 | `2aa422da1ec30bebfb72ba5fbfd384e7` | `a17dce69a536283ed5b46ed1acff1b81878f619634295dff34413fcfe865e1ef` | downloaded | 11.436 |
| noisecapture | Colombia.zip | 52534227 | `005d69fe5cae322b3a21220a42d963ed` | `be676ebffd31a04908aa0fef7a599c3954ea949e2d275c0df06941becada248e` | downloaded | 4.983 |
| noisecapture | Netherlands.zip | 48857644 | `bb527a6871d26f98f265f2631c15c9ce` | `4be34d640e235f23f97f93e63fa0bd57d458e051342766c4c4587f3f0aae5564` | downloaded | 4.876 |
| noisecapture | Austria.zip | 47364294 | `2e948d152a590d6e50298705402d6bdd` | `a93e975557743e33f37413464755848a858dc317f50695016c1b1889fcc7f74e` | downloaded | 4.951 |
| noisecapture | Belgium.zip | 37893139 | `d60bc01d6233570902a2c991128c1002` | `bfa1f2d69a05361614e16d58af3412dd8ec9444d07f40d54ca6de0558e6ec53a` | downloaded | 4.028 |
| noisecapture | Brazil.zip | 45844212 | `35c0a7bddcbc45c1a4a6e5672511fcdd` | `540aef978fd95a0fcb9e09a2a59bf91ba0ee98b2a85d771f3d7f6580181df9aa` | downloaded | 5.265 |
| noisecapture | Thailand.zip | 33939832 | `71853d2e54edb8106a0b3616893b20f4` | `d056af810b8a6933051d095b88d167ea62cf181e4eaa733d80834b64db88b4c0` | downloaded | 4.093 |
| noisecapture | Singapore.zip | 31512558 | `8be134a62c3ce41deb3b7d294efbe7f2` | `23d8234412aa5225c91b15545b1152291d7c7e0f8f29d703fcb33b038a148d81` | downloaded | 3.72 |
| noisecapture | Italy.zip | 31402272 | `16353b73a270408955f7543b8cb2d004` | `a583f61ac498ebc619709c29212f875be31db82c795e22aad90b1bd697449cc9` | downloaded | 3.979 |
| noisecapture | Turkey.zip | 24516660 | `52fabee712659a36d50c779cd01c089d` | `b60eb95f6f1b7cdf73118df5939865d044572cbfa5b435064b83147282909655` | downloaded | 3.441 |
| noisecapture | New Zealand.zip | 25411956 | `90284964259f9a63ca466906a17cb58b` | `66eda2e9e1abeeeae43c6e5bedd950de066bcbd606e566f78e016230a607631c` | downloaded | 5.882 |
| noisecapture | Rwanda.zip | 22754828 | `606216669c648c3a9166508eee5e000b` | `e9b2f962c5d0335273aee908fccc14abecb7770b55e7485d0ad8a5855a9912dd` | downloaded | 3.126 |
| noisecapture | Iran.zip | 21149215 | `557d39f02784b400a066ffe82fce3e8d` | `678e1c5f44cdf3107ec181b1ed8ba1883928dedd09713615162662c3e00c0202` | downloaded | 2.978 |
| noisecapture | China.zip | 19100109 | `845213bc0b069b3d4a96cb2eb9ac2eb7` | `084b599fdf21039aad28c8dcd44a5dac4f7bbf38667d8a3b12fc8cb930d875a7` | downloaded | 3.752 |
| noisecapture | South Africa.zip | 16687693 | `7b37d898cc8ec728c945cf2cf376d72c` | `dd4b6c0c62b5226d44c8a3cdf3ebbc9a823a21d4ed06d57f6b102760ffd743cd` | downloaded | 3.077 |
| noisecapture | United States.zip | 1098078043 | `2b80d6f3cba8582790cc0711dd656e6c` | `678359778869971715bb1db259dea29de8744507107e294d0c9dee605f52419a` | downloaded | 95.591 |
| noisecapture | Kenya.zip | 15305481 | `f57bdaef1f2f057ba1109f15cd4fc435` | `9be5f266461340751064a538d03e48f7ab5982cbacf14afe78c87f79a8927106` | downloaded | 2.907 |
| noisecapture | Romania.zip | 16654182 | `a87967f49d66fe89468d949af2e65529` | `9b5406356f7802b3b4390269f93255e56216f25c88f36ec0fac90e71c422312c` | downloaded | 8.301 |
| noisecapture | Egypt.zip | 14738002 | `26002806d8649b32ed4e4349679ed422` | `2c46a4c9adf7c745a083f52fc22019c49beff42508c5402bea44f38e508eb60e` | downloaded | 2.822 |
| noisecapture | Pakistan.zip | 14608200 | `09ac0cf17907d95318ec3f94657a8e83` | `8078b3699791c0e7cbfb9d1ccb1f62c2e720ce92b8dbb3a2b4dda05bc75f27ee` | downloaded | 3.288 |
| noisecapture | Peru.zip | 14378297 | `e5646b1eabc03b731e1fd502a3aaa497` | `b965e0d7ffb69ae8fac427e6f0cd9484e3832d8377e2be0ab9dca83781c1efa8` | downloaded | 4.024 |
| noisecapture | South Korea.zip | 14154517 | `0076bee47d90310db05a1ea5425924f1` | `016936b7a375f21f0f42c73bfb18fcdac75a225e81d6637fed5f54f3de81851e` | downloaded | 2.777 |
| noisecapture | Hungary.zip | 13607845 | `27f657acca94402ad6c072d8d90f748a` | `fff25a5d42324bef6a408de889f6afaf850f96b90ecd3f92d435e9b15905e84b` | downloaded | 2.768 |
| noisecapture | Chile.zip | 11431669 | `e74ca515244e77e2a62e741a493e4866` | `181671a10c5eac3de039c76d9e10808f47b26fec8fcb54380de90371404f26a3` | downloaded | 2.728 |
| noisecapture | Argentina.zip | 10576673 | `0cb5a18a024f90b03d634418c98961bc` | `3a7ab45c17a0ea946584d7b1adf224dfaf36e18b95220e064538cdad8d75123c` | downloaded | 2.492 |
| noisecapture | Bangladesh.zip | 9986460 | `0ac47d615d649650a656c0f20aeb65c9` | `a43355e405dfd019b0426b63da01d9c8e1dcada97bdce9515073db089deb5de9` | downloaded | 2.485 |
| noisecapture | Algeria.zip | 9633701 | `9645f17bf941ae4bed46a516eed45146` | `06507dfda5474c271c513cab3f417f7743b6f38faad8136db1560ea45dfe4bf1` | downloaded | 2.578 |
| noisecapture | Albania.zip | 12625587 | `42072e873d9de7c8eb2d2efcd9523dbb` | `1665e2bbd5d8d8c99f5cd507b70393149ef7908b71c0a5a253a9df6f7c914527` | downloaded | 7.14 |
| noisecapture | Russia.zip | 9318642 | `8ba7c770ee08212ff6d130223def6368` | `c9ef8d591db074ff8b3b475b9a5431cc831670b909fa12a6fec00223733377cd` | downloaded | 2.373 |
| noisecapture | Portugal.zip | 8581877 | `9c06cf53744e9f76b38fd20f46f2c123` | `7b6c41add059d07a297105496a4b9ce590f1f4e3cb969f6c2091ba5499cf04a2` | downloaded | 2.689 |
| noisecapture | Lithuania.zip | 8072159 | `8eabf260ce07ca5e0061b4ededa3c8b8` | `65725688277ff072cb7ec2362c95dddc50f6f5000844af5a84b0236e38da94e3` | downloaded | 2.573 |
| noisecapture | Bosnia and Herzegovina.zip | 7918860 | `cc5c9b6aeb174b5f25f1bf10bcf7db5e` | `0b8e3101a8d266092dba1c40e206417b78dc5709728d2b031b60e649378d0a2b` | downloaded | 2.493 |
| noisecapture | Morocco.zip | 7887544 | `fdc9b37d6f198aa9af96e3528f83091b` | `ad3fade8657b3233392928c5e7e453f4f643b731609f3338b196ce4aedaf440b` | downloaded | 2.508 |
| noisecapture | Philippines.zip | 7797503 | `3569fe2c9d5de40667317c07fb21738b` | `e132edc10ea1e9441d3c532656b2da5bfd713ea6706a9e77727a0e149ec0fa5f` | downloaded | 2.436 |
| noisecapture | Cuba.zip | 6415915 | `fbbe583921dd713db1d5dd6419faa50c` | `7ee31439cfb4130a26d4fd496b4834b80b1cbdf4835b748383237369c2b24668` | downloaded | 2.294 |
| noisecapture | Botswana.zip | 6050572 | `6fd865247767e6f7a0521c5a7d105f19` | `4ce1070cd6261d0bf7571804b431cd8bf75b1cff139225600e98fcf06d657140` | downloaded | 2.214 |
| noisecapture | Saudi Arabia.zip | 6356602 | `5732bafd29102f8f43499b40120488de` | `c902933ca1dda768a670977c127270bf86612dd5a083f0f126e50bb6b2c0df14` | downloaded | 3.534 |
| noisecapture | Sweden.zip | 5534624 | `8546b22195b6328b71131df0d1fef210` | `38d2663722f126395f0df1cfcd181c45139d87842055ba8c1cfdd8bfeb1f9337` | downloaded | 2.211 |
| noisecapture | Israel.zip | 4929655 | `fea7ab464661a9c66d95cc6bea8b0ef2` | `bc9b531ca6fdde7d1038eab3e9885eddad788e0c0c8972530c02c02ceb799c61` | downloaded | 3.137 |
| noisecapture | Japan.zip | 5598110 | `7f49eef98b35dae31bb78ee1d9f7a5dd` | `7e6fe54f973efbf934a365bf7740fdb89b70a089cfc32df3a817812ea2ea4f85` | downloaded | 5.428 |
| noisecapture | Gabon.zip | 4691420 | `da21c0fef0d7ae15dedbb8be0d66e95f` | `b3356702d34cbe37a1cf097a494e0f00587e1a4c7676aae6001619c3d5baa61f` | downloaded | 2.217 |
| noisecapture | Finland.zip | 4637494 | `40c6297e1c28d099605b8545dbfc1f56` | `130df86ea71a56a8e35546e19ec61f6d7f01a3e9a9e0f363b5b105ea4ef8e58e` | downloaded | 2.196 |
| noisecapture | Indonesia.zip | 4654935 | `b9c549969468f0d2507f11ef163689f8` | `b992b6e48684fe994e580a315ac71a4d5bdc6f49140350c505fafc877ef7a516` | downloaded | 2.188 |
| noisecapture | Denmark.zip | 4235277 | `9f17906b9c212a93e0399dde3d6f396c` | `c03472d6379c56a00b06c7e45810faf20116a0f2f0f6c2563e47348d18348480` | downloaded | 2.212 |
| noisecapture | Taiwan.zip | 4342186 | `36b1deb5009c8cb344e22f407ee2166d` | `3cbb84cb2e6cbd1b8fa6ef50dcd7a4d136be19d4abefa264f5df70329182e658` | downloaded | 2.367 |
| noisecapture | Reunion.zip | 3995818 | `1a77f8334d57f4124e10dec766875cd2` | `55fcfca99e9de14a14a217529e43cb6dbd67d4120e36ef3ff09e177f0737e90f` | downloaded | 2.208 |
| noisecapture | Ukraine.zip | 3744229 | `c288be5e4894c303198b4cf5bbda044d` | `3eb339a3d042af67f674ee363b7470af51559570ab163618a61c56ab9acab011` | downloaded | 2.165 |
| noisecapture | Czech Republic.zip | 3705677 | `16232823bdf3678af7cdf6aceb7ca16c` | `65cd0512f13fb532cb547b0d30fae80f118f018dcdd1042e392d0a38fc4e93ae` | downloaded | 2.123 |
| noisecapture | Hong Kong.zip | 3557460 | `2197c5e7e78fa487719acc777592a1e1` | `59291c2d40c763a3331379fc440b341c6fbb937c22f1b0359754d210d42dc338` | downloaded | 2.179 |
| noisecapture | Jamaica.zip | 3376564 | `6a19d5a52cd52bbe2f046b743d10e116` | `ba8cc3953453fd933c6b30dff40c1e854d86845f550fbd38529a43b94b6d3d8a` | downloaded | 2.135 |
| noisecapture | Palestina.zip | 2883758 | `c21a5b11ebd3ce03cd665ad62264d094` | `1985ce101af07624fa076d9e751c2b36b34cb9b9f27c68ff16bb9e05b376c225` | downloaded | 2.143 |
| noisecapture | Ghana.zip | 2377948 | `2c9e24e2d94b9d6d23d99619e3b4da48` | `f68cf5884f15487dfea11cd878da5635e51e5ee38db4ec07ce24adf9912a02f4` | downloaded | 2.009 |
| noisecapture | Vietnam.zip | 2287110 | `b14d3fa733e0a06fb76f41944fb7be6f` | `991a79db01d779ed6925b8215be5de3d11e7648252f08ab9aaa9ecca76c1c2ae` | downloaded | 2.128 |
| noisecapture | Tunisia.zip | 2203558 | `f594a52e2303b65f31259b37a484f6a9` | `feaadb48287885d718e0c4f3659efc37ffd2759aa301308bfa1cb42b43dfbfc6` | downloaded | 1.982 |
| noisecapture | Jersey.zip | 2070092 | `01a4f43585c89ea8850eda52536b7f37` | `37c86245ce2c13cd0b99f7c274e731b25139917825c82534e43d514a8a1ae551` | downloaded | 2.018 |
| noisecapture | Nigeria.zip | 2100484 | `a390d8841ed1c3053e4e1600d39c6ee4` | `3af0f338b5c9e9a3d39803b32f1ff7003fc73cd81818953ce0a26063e5e8955a` | downloaded | 2.003 |
| noisecapture | Bulgaria.zip | 1949240 | `e2bce13b2ba0ccab93341a459f05bf97` | `46dd3aaa390e3e79ebeeb628cf748fbdbb6d11c6afcd859c4f2f27de47c56260` | downloaded | 2.036 |
| noisecapture | Costa Rica.zip | 1950705 | `5e9617631f197cae6cbda6233b831a6c` | `5229cf17719e4f0d2565af4daf4f5009636e22a20fba29905417d402c32b8186` | downloaded | 1.962 |
| noisecapture | Martinique.zip | 1949522 | `ebe5e16deb0a96b94136958e32fffebc` | `d98d66d52a40953d76a9deee35690684aa7aa02f26203ae09b4ad301349c092a` | downloaded | 1.965 |
| noisecapture | Kosovo.zip | 1759278 | `75d38a5e9fbb6b3e1f8d8b5d5aa6ccbc` | `29f757d563bff781d78b751732a02b8138040387a9fdfa74632847afb0f9dfc5` | downloaded | 2.003 |
| noisecapture | Panama.zip | 1768653 | `0c75b1e69c81fe032a2236f0af7b7548` | `d96314c82178657008ff95a3dcfdf045762aed015a81a923fab1c635167791e6` | downloaded | 2.006 |
| noisecapture | Bhutan.zip | 1643344 | `e6212a2d31a1f76bc9b624b86280c265` | `9c3c96fe84f1a89484740f252c9bbbbe996e4aacd5d7e31b64fb6c536130216d` | downloaded | 2.011 |
| noisecapture | Myanmar.zip | 1434487 | `798e172bc3118436676c31a62c713ee1` | `f51fccd152efbdd7d07f2c0a84709070d1073c00f78eb7921981d32e25550b9f` | downloaded | 1.837 |
| noisecapture | Cambodia.zip | 1566656 | `7317d959c33b66eda3049420450df80f` | `da25c5fd455c35645366c92efc495ae4fe1e102739c7cef4e697cffe541fc141` | downloaded | 2.0 |
| noisecapture | Serbia.zip | 1498364 | `e6a631f6934f4bcff0a06631de8255be` | `d543abd0e8462f7ab95184f0e7502337b899aa8c46e074fd4f04dee028352bc1` | downloaded | 1.815 |
| noisecapture | Bolivia.zip | 1384473 | `292c3adcb1534e0537ffc3c77c6020c0` | `279a4a1914ef4b1d604f2ef5d151086393c8bae2c96f866802838a31ab7a871a` | downloaded | 1.805 |
| noisecapture | Estonia.zip | 1323404 | `ed20a4fd5ac2d2364cb2688568488253` | `d17064f96c4ac11b7384f3c3621ab0930d965216217719d6c2b45a7a2db8b926` | downloaded | 1.844 |
| noisecapture | Luxembourg.zip | 1404650 | `a0170e6b5e1e4f45612725e49320cc45` | `be6e2608fe4b25dcabfce668f627a41980326224baa7c3f38d3e0fc410ed5821` | downloaded | 2.103 |
| noisecapture | Slovakia.zip | 1360808 | `add02e201f25ca4b3ae8882773daaaf5` | `48c1582b141d4f4b170a1d0eb444c903bea62dd0fa4a4e2f097679108eb43b76` | downloaded | 2.041 |
| noisecapture | Cameroon.zip | 1229767 | `180df7ce1cab3da1ac2bf817144ccd42` | `1b3a515cca54f48c2b4e0aef7ca6e953fcf0259a4c7da7ee0ca0e2d5840ebd84` | downloaded | 1.974 |
| noisecapture | French Guiana.zip | 1241226 | `16f44c4aaf8fa6835d78bb6c0176ec2a` | `f7a03c0f211ea622b3026c8799e5c16c4b24bb77c7bea61cb1eff83e3054c8f9` | downloaded | 2.173 |
| noisecapture | Malta.zip | 1273737 | `d041f89a831ed595dc086ef992be054d` | `069bf56d2854759ce5d72e0fff105039e5d3bd3ec62ddb6e85fbef31a69f3271` | downloaded | 2.006 |
| noisecapture | Ireland.zip | 1105823 | `7f220bf504ba1e7731aa5348a01c5ff2` | `b54c313ddfc3d7d28212d6fe209ab9af9e2a11fb3fe682ee98424048435882bc` | downloaded | 1.824 |
| noisecapture | Belarus.zip | 1080638 | `c50ec31e7b56386ef5bc6c152d6ed0c4` | `0a4c6b61a6cfcb8325da6d2143619dbc7bc3102eaa4244fbdb6135332c75434e` | downloaded | 2.108 |
| noisecapture | Qatar.zip | 1081610 | `6b7178e5ce59c7f64cb8033ef2cdd116` | `d94adfa87a9c11045260e1cbe620a038aaea38a0954c05d9905aea332b870250` | downloaded | 1.802 |
| noisecapture | Côte d'Ivoire.zip | 1076244 | `6a71dda97284096f9be9980fdfa98369` | `51fb701c2bd2159ac07984f97e5df7138de75349c3c42b5de6239c9cdc6cccc0` | downloaded | 1.864 |
| noisecapture | Sri Lanka.zip | 1080935 | `b3927309acdd6d541ea97d0ec336c0c3` | `a86d0a6370476758c5e4869d5c521e545d21d164b1b13b83ef4b2e34785dbf17` | downloaded | 1.964 |
| noisecapture | Norfolk Island.zip | 1004323 | `bcbe45894aa8b62f2661efc2ca221cd4` | `b4d79965b9cd25d4a875548dacfe96490d85076be87d0d6125c00c0e078c2706` | downloaded | 1.835 |
| noisecapture | Monaco.zip | 904534 | `f89e06a63ee69438fbaf89aaf80a35aa` | `2fa801e1c02b80d75285d8449d538a8b9513cbf70b8c1b431e7635357aad537b` | skipped_existing | 0.276 |
| noisecapture | Namibia.zip | 1001357 | `947f6998d50f491dc0415d2cff680f10` | `c40f77d0ccb1766ed6fd64af64976c99b09ac81056cdd44d3f77cf4eab4a59e5` | downloaded | 1.839 |
| noisecapture | Latvia.zip | 935616 | `96d8c4cfaf24ae5864541701701a0248` | `25d9b6f725ab42ae31ded83b731dc743636efabb27c4b2e92cc3ac13de03bb9e` | downloaded | 1.803 |
| noisecapture | Democratic Republic of the Congo.zip | 862180 | `9affea3acf6b77e3ad2bd74e786b0f37` | `85098e2c3f51554e72b913c39f721c7c1291e3ddd6310e1924f0ebf99e161f87` | downloaded | 1.785 |
| noisecapture | Nepal.zip | 891146 | `37f99c951915fddae72079bc9c8acc5b` | `560f83289a14de9d360597f055e546b11660678eb5fbda5772a10ba21def61a7` | downloaded | 1.886 |
| noisecapture | Benin.zip | 783249 | `2ece8cc308dda389e4c31de73d078f9a` | `047729483e43e3aad7b2d4a3165b49ddabd6bdd398bf833823b36508765e70a4` | downloaded | 1.661 |
| noisecapture | Oman.zip | 787567 | `49094cf2613fc58059fd0d7ce6d2f9ea` | `aef9d77ea4fe77ceed3d38a98c449ad0e3686fc872a92e1738da864959a47355` | downloaded | 1.863 |
| noisecapture | Guatemala.zip | 751804 | `1f20c7fde8c9f808461065074541e2b3` | `8908e6bcf9e8b5e2fe58bb3363b8064b19c47e1956de453bdc6189a97b0e3177` | downloaded | 1.643 |
| noisecapture | Lebanon.zip | 779988 | `06ae4e8b15e11be17751b58724f8a822` | `af2686440f5d14ad011f83c2743b6f8035c0198dacf5952872cb91c7f31af9c7` | downloaded | 1.839 |
| noisecapture | Tanzania.zip | 706859 | `78d2afc7f8ad0b8de6b00b723549f489` | `87c976711a741abe4b02d7cabff79a645ca5ebaf2a2d7eedb4e4481d08794928` | downloaded | 1.644 |
| noisecapture | Guadeloupe.zip | 629650 | `8b0ab2eb4218e5fb42aaacd5fe6ee19b` | `06abc59904658066fb86e92d41317bc1c91f028413986b8df8977eedaa62b5e1` | downloaded | 1.636 |
| noisecapture | Afghanistan.zip | 567665 | `920de31e15819cabce476be826945d05` | `13927e679f5454001ea18723b49c4687c61b5254393b2e80abd4d709cc2eec86` | downloaded | 1.627 |
| noisecapture | Venezuela.zip | 599674 | `9842e0713dece6779f254810549ecb0b` | `2777957f1a0c7da71782373a0846dbedd73f51c694b103279f032135a95fe484` | downloaded | 1.876 |
| noisecapture | Uruguay.zip | 502852 | `4753dce64941684fb30533899321c951` | `777b19d46ece952a75bbfd66c3915b73305f5cc6989c6b7988d1df50b6dc593d` | downloaded | 1.619 |
| noisecapture | Mali.zip | 526410 | `cd88068b0e4c644c7beb47561ac65617` | `6fb7458b26d24ced008d4953e260a3e60f631063083fd77c4ec1759a810cd619` | downloaded | 1.832 |
| noisecapture | Dominican Republic.zip | 489396 | `6b8245afd340aa535e04b2726b48ea13` | `a2aafd6169a0c007d4d61a70a5719a2efbc953eab6b8687d76ac65890a7dfabe` | downloaded | 1.633 |
| noisecapture | Kazakhstan.zip | 449698 | `a03c59e01c3d92d075bde49d71afbc17` | `61615260cdd181efb3d3efac9f1fafb4b1b7861d7623fbecf2d3156ed26e11fe` | downloaded | 1.702 |
| noisecapture | Jordan.zip | 449285 | `9864f762a1c1bd457aa748e8b6946fdf` | `40a3df630ae21a6a413ad8154a22c17bbef95f1085a4b02cc4bbb0990385ab61` | downloaded | 1.653 |
| noisecapture | North Korea.zip | 415296 | `5c8f7ae883c39fc463238ca22d713bb6` | `1f17ade999207efca5cea0ab9a49edd7ff7b4d611b6515f095a25a8990f8418b` | downloaded | 1.688 |
| noisecapture | Madagascar.zip | 401194 | `c19c102dcacef7872c73af2e96f92b69` | `1cb0e53591390d687dbd99b2a1ea7bc2e7960bbfc041ba95ce7325474ba0f6e9` | downloaded | 1.636 |
| noisecapture | Mauritius.zip | 396843 | `2d4bbdd086ba22e9d6189e53fda62168` | `761933c9d2d0e03e2272192db2a9c1ee352723d5059cc8f5a0bba57276c62df1` | downloaded | 1.682 |
| noisecapture | Iceland.zip | 389904 | `fe064a15f7565e26a4046365d42a8bdd` | `2e495839fb422940b816b27bbbbdee4f91e4d57da43b4e309255a7055a51fd5f` | downloaded | 1.635 |
| noisecapture | Iraq.zip | 388437 | `6b5fc634c015b5f5f2fd5758e4167fd2` | `3869493c324479ace3f37268c953a40ae33619bb2df0e3c9ca394c5188aadedb` | downloaded | 1.602 |
| noisecapture | Angola.zip | 383919 | `a5720bf0f3e5498dd38f8bb30b3ae151` | `6b3d6d4bd3a0038a92f24a6b97b6afee5b4b0908a49072223ebc1e6c20153eb9` | downloaded | 1.471 |
| noisecapture | Burkina Faso.zip | 371778 | `4249378ae3cc7f98f3d2f347054cc2a6` | `9b6c97dc14d85bfff5ec56eb71255903980035ba4ddc225d32053c24c346706a` | downloaded | 1.521 |
| noisecapture | Puerto Rico.zip | 337991 | `7229e7e6bbffe249fa283ca40bc18e3e` | `fd28962708a4df9913dc1299c9e4c1aacbcd1071acfcc435d5e8f198ddaf84d2` | downloaded | 1.503 |
| noisecapture | Laos.zip | 353642 | `8eeb9ae32c5752f441295a8e4815946d` | `1c26321776c7b4e35e6d30cc3d57119a37af952237411d6ff0565ff6ab1027fe` | downloaded | 1.645 |
| noisecapture | Guam.zip | 330801 | `1bcc16fdbdfe336212687618634fb610` | `59ec1d9c5107bf136d7e98f1ff339d487d66a1eb2741c0ad620abd272ce91f22` | downloaded | 1.48 |
| noisecapture | Georgia.zip | 330345 | `1f8d028985b038ed9a9cafec05341a9c` | `4b21fdad56245450e083fec3e895ac8fb714eb50dee81814ed0b9fb880bfe60b` | downloaded | 1.48 |
| noisecapture | Ethiopia.zip | 320590 | `cc50673d278cf5064ceffe0aee9b0046` | `388bf069047f9844be8c9909f2eb7213b1a18a23dcd6e3cfb21d672ede083c3c` | downloaded | 1.624 |
| noisecapture | Haiti.zip | 321850 | `0521c546805c4cab833638f44cc32325` | `bcb61fdca268543cc7f87c46627eef611f85686c601bc3f5942cde5ad0671332` | downloaded | 1.758 |
| noisecapture | Senegal.zip | 317690 | `d273a95ce0fccbd356209a63e793c059` | `d29cf99bd050ccffc812c41bab0fa37ea54093867f4f6f40b8ce6b85a5e5df7a` | downloaded | 1.576 |
| noisecapture | New Caledonia.zip | 314152 | `31fe0ca759c785491d96cec43a954e07` | `196840f7f24f10c1c3728590ea727fdad032ba97cfa534f88c4bd2c63f585e42` | downloaded | 1.469 |
| noisecapture | Paraguay.zip | 313938 | `24e361e71d5d496fdb72a9cc68a90458` | `64b23e6589c68872bc779add73c6357732120862436c5c907c8f0890250b487c` | downloaded | 1.494 |
| noisecapture | Cyprus.zip | 306584 | `4088f508f91b10cde45c5ab9afb55216` | `211794ba9a2b7a8d688691e5a335b1c2dce346120820fc08044e5eaeab601e30` | downloaded | 1.464 |
| noisecapture | Comoros.zip | 300982 | `d6bf0a09618d7ad0bc689f8583e29000` | `38bf9d47e2705da041371061503122eb55c8f68c18828c73622ff105b9a12d7a` | downloaded | 1.494 |
| noisecapture | Uganda.zip | 292647 | `c148b177c613e412c1e9b1b29344896d` | `9735475c5a0df495dd7e5e70e452eb7444dfbc438d86463499c57872474e7aff` | downloaded | 1.473 |
| noisecapture | French Polynesia.zip | 263439 | `621d89ab30c8a092fee3c03f3987eed0` | `7113a129542b337ee8099538cbc3783551c7b401f6e133ad3c581ee3a7474dd5` | downloaded | 1.472 |
| noisecapture | Guinea.zip | 253937 | `4ce4ee4d4ad0bc13772ec752f9661d1d` | `a4bc6d67a57ed84b561a004ee740c973b70692766e83f4fb6c47389eb6021a1d` | downloaded | 1.672 |
| noisecapture | Mayotte.zip | 229017 | `28f265e73cd68ed0d38cc83d7e451438` | `5b2c50646a3c71b3aff330953289b6fcb09ab09920df9a40b835e3c72d357f58` | downloaded | 1.485 |
| noisecapture | United Arab Emirates.zip | 227705 | `79d60d39c90fe44c237bbdfead341c17` | `098d064e2ae4ef7a28976ca1735ea3794bc94fd115e5c636319fe3257f383962` | downloaded | 1.52 |
| noisecapture | Syria.zip | 220067 | `e047509661b00c2daacb5aa2c79925ac` | `169750fb7d53ffb123d545e2bfc4420b6ccf15140766f20b1d422f6e3b262299` | downloaded | 1.565 |
| noisecapture | Liechtenstein.zip | 211107 | `437dabffd921c56973268c3764d5c6e9` | `606418aa7545dd75f830dc5a6b228699253ca4dce65a18bd64ec71ad6959a24a` | downloaded | 1.475 |
| noisecapture | Timor-Leste.zip | 197211 | `01d25991e201f83d23a2f8d6de8566c0` | `4e3e6175a5ab4aa7f4a70dcb7bcf1f01f94ec7bfcf0009a5fcf2103a0e0e5f38` | downloaded | 1.51 |
| noisecapture | Virgin Islands, U.S..zip | 190405 | `55aeb5047875cb97fb145a38427fb3c2` | `23edbbba97dc2184b20892b04f78ad5a13f8f1de5048f0af058f13e84cd43971` | downloaded | 1.47 |
| noisecapture | Djibouti.zip | 184958 | `8142cc15dda6db9ce8496c15d540247f` | `af7625a775feb36a8e3baddb887ac277f71345e3e1cecd66fe25a35317edb7d7` | downloaded | 1.447 |
| noisecapture | Saint-Barthélemy.zip | 145495 | `001631fa2cd3737ce8eb7fafa5270949` | `f570a000e91822241a8495e5354b638de325271b362f53d0d154ec74fcf0f90b` | downloaded | 1.402 |
| noisecapture | Maldives.zip | 124266 | `99caa82ce73b5beb677dffd406c9014d` | `3ba04ac95926477b7563e7501c8032a25cb07897816b367a0a7796689212e9e0` | downloaded | 1.36 |
| noisecapture | Swaziland.zip | 123391 | `90793e66a47594902abf51a695f0e870` | `e61457c75266815bb0c43763a619af1e9bfe4a01f6dab4a6a44f0fc0a9d36f3a` | downloaded | 1.323 |
| noisecapture | Honduras.zip | 117857 | `2a99f05654f8ae6214dc0d6b5b81cc72` | `f5a4fb01dd88ca8346755a289c20fee2d3f32eba9d25bba82bd5e914c78d4751` | downloaded | 1.334 |
| noisecapture | Central African Republic.zip | 117406 | `2728f0cc0a2f3b739cb8c255734d0c4f` | `97be000edeadef26dd2cf6acd72e2560766d92e76f7c3f68601a1443022eaf6e` | downloaded | 1.305 |
| noisecapture | Brunei.zip | 114515 | `9ee8687c238bf4b3e071c6e25610b4fc` | `9ade120d53c33903658a4fdbd579c9fa52c71ca1d7460975c4169f943771baad` | downloaded | 1.307 |
| noisecapture | Eritrea.zip | 112022 | `edf7918bef7e1eb2416469a78d2fb725` | `9f912c3577bf03c0958d291bfb941c4d513792199c2fe28a42d50a0808f15fed` | downloaded | 1.295 |
| noisecapture | Isle of Man.zip | 111763 | `9098490ca254b6fd1864272212f1c24e` | `3925627235313d6a1dbad3331d2748bf84e5838d0148543b9fa44353ec532c1e` | downloaded | 1.326 |
| noisecapture | Solomon Islands.zip | 103813 | `d9a6567bd45d8696eb8be923f6a9f72c` | `6b16b5f5367db133ae54a29b4990b225d8536f7641291808bbed01f22b3643e3` | downloaded | 1.301 |
| noisecapture | Uzbekistan.zip | 95956 | `6ff6f649f01d16e70d3a0ec4023daff1` | `2ac88befcf284ab18d49502061e56f4d6be7d21643221f78042725a5b877b6e4` | downloaded | 1.142 |
| noisecapture | Guyana.zip | 102413 | `675f0c66f148c471676dbc3369f84ad6` | `e684097597b8c9a7fe1dd3b0783df20d3051f843a5075e1c6b663a5d3eb3e686` | downloaded | 1.443 |
| noisecapture | El Salvador.zip | 93496 | `26f80f6c02cbb2fe79ba979227b5b3b5` | `dee9ddcb1417bb95a93c2e8421148fa56f5d229b51efc0952330c555729ebe5b` | downloaded | 1.147 |
| noisecapture | Trinidad and Tobago.zip | 84785 | `56e7dc6f66e6da808cfc707f508f2eef` | `45336775cc911a763187d51f0d4ee35518ab8f78eb887fb449c91260786c8afa` | downloaded | 1.148 |
| noisecapture | Togo.zip | 86743 | `985b26fc9b979f6a2a645769cfb45789` | `e0fe577fe807c91fec4683de381eea4faf7c7c067ae08f2f6c0914da827e6b55` | downloaded | 1.234 |
| noisecapture | Cape Verde.zip | 84337 | `5b3970c9e621a320c308edc9196163e8` | `72b831b9e2d98aab4ea15b03433db44c193aad1a3be2523fcb57acbdf96adaab` | downloaded | 1.146 |
| noisecapture | Moldova.zip | 82512 | `de3e9faab4b3cdaa6192b2cb217eff5b` | `c536b66f0c4b35ae9bff6c914f5e3e53466041e56fc00a232a2a6b581dcb9459` | downloaded | 1.148 |
| noisecapture | Bahrain.zip | 81983 | `7108ac0cba4d6e8e3fc465dc5418d7c0` | `e2f9c2febca9c889ba90e59fb6da56fc6eeb787da3313c1c0672efc4f13b4c04` | downloaded | 1.148 |
| noisecapture | Chad.zip | 78576 | `d55ac9e754a416a3acd693c58bbeeb26` | `d89065d01a28f1ad61959567114bda4c8c481a334df2e89a26590da156b994dd` | downloaded | 1.176 |
| noisecapture | Kuwait.zip | 77322 | `b88a8b636176d37479efa772682cea6a` | `5ed034b93a7268456ad1f51a3eb13e0bf406859306a3978c41ba9d569d9d4845` | downloaded | 1.152 |
| noisecapture | Caspian Sea.zip | 72962 | `b90767ac9254afe076427f6c0db8d062` | `225a1babbc395b2387aa798eb7d1738fdb464bebca5242a0c88fade6f3dd0ad0` | downloaded | 1.163 |
| noisecapture | Sudan.zip | 72899 | `99517ce45ddf4430327236b1f37b41db` | `6c419b8d575067ae12d6bbae39314ef2b8e35c08da34af8ac483f8c755156e7d` | downloaded | 1.173 |
| noisecapture | Svalbard and Jan Mayen.zip | 67239 | `d3f3f4b21df7b7132c98308d0ec3ccc4` | `b9cd6ed8356d7448cae16571718fcbdefb2399318605b288b60565a1fd11650b` | downloaded | 1.148 |
| noisecapture | Libya.zip | 65970 | `c49d57b2aedb985b505d933bce8c83db` | `c92d4d7758833943e5f21a96f8b577dcafa88fca76714a3a0b35510834bc451e` | downloaded | 1.144 |
| noisecapture | Zimbabwe.zip | 64312 | `b99bd594dde191935d8397c65d68e054` | `881d1115d061250be9c12f5a8219211d1d6747bb72cab2bb16ab85912a0251f1` | downloaded | 1.151 |
| noisecapture | Northern Cyprus.zip | 59009 | `62f558f7fff56ea63ff53343f3b01382` | `d24b1117e235de7e59ce77a31865adde53412b76dfb7886adace469200880400` | downloaded | 1.2 |
| noisecapture | Macedonia.zip | 57955 | `eaa0cd104be8179b0e1d1abde8dbb12e` | `590d3c8e565b0ecabfe7a10c6144971fd19e6816606781e8e4d6bf89187146d9` | downloaded | 1.154 |
| noisecapture | Liberia.zip | 51428 | `c2851b12adf858aff4d32c7e0e664e3d` | `fe745b1505700e654c43b1e15aaafd0de4fa2756994d4a7858834e7255062af5` | downloaded | 1.209 |
| noisecapture | Nicaragua.zip | 50832 | `121bee09b29c84998515575da9edcaa4` | `f644098b0875f820657b4e969f35f6d55f0b677de6a9debf1df2b13bde7e21b4` | downloaded | 1.154 |
| noisecapture | Republic of Congo.zip | 50369 | `1694ce2e80c9036f47277f5ea62a1c38` | `94895c925499199d1b896a2173ef75e5609585445b750436f569a55de8282fc5` | downloaded | 1.147 |
| noisecapture | Yemen.zip | 48438 | `b3923400a8c14db2df30631ee7b2e27b` | `466832773ed60583c795147b956fcf6fa8308a50906dbdd46155ded43b94789e` | downloaded | 1.146 |
| noisecapture | Zambia.zip | 45220 | `1a98ab34d9133d9f2eb16893ff5977ec` | `9793fbe48e30432ebe488edc5bf0b01e89ffbe385937885ada4055c87b4f42a6` | downloaded | 1.149 |
| noisecapture | Azerbaijan.zip | 45144 | `9b673d39683e6b9862da53242d8ce904` | `372bf30829a83accc7b7f7bb92a2b0dcd8e9e6cf8f6cee1ede6c4a745d38a8e4` | downloaded | 1.184 |
| noisecapture | Armenia.zip | 40904 | `0ccce388827cf9840de0083a5105ec69` | `e9edd54e0c93a19223924d102a6f7df55d4bdf960099474c09debf183ff11484` | downloaded | 1.148 |
| noisecapture | Montenegro.zip | 41331 | `5925764320d3db1ea9ebcde37b664e61` | `631892f90788a6e1b0be21bc830d68944723e2eeb539a57e36fb6b777256f41b` | downloaded | 1.16 |
| noisecapture | Macao.zip | 38428 | `4889f8a36c33f090fafff57ca4301335` | `2f7f08212806d72a489828e298b9646d56df5dee987cf19abbd9ac0db5ad3be1` | downloaded | 1.085 |
| noisecapture | Somalia.zip | 34958 | `2bce97d8cde7508fe0b632fa5d83f56b` | `cee1b9d84829513d79c1355879251aa47359ce94a2e62ff16839cf7fd8ba76f6` | downloaded | 0.983 |
| noisecapture | Suriname.zip | 32016 | `cdbc20b69e71541bd87185247e6207ac` | `be45886e9f794baf96c7e900df2b837fd47d9eafbaf43467f7718f230fe318c4` | downloaded | 0.985 |
| noisecapture | Papua New Guinea.zip | 32030 | `4152a0975c77218629bf6ae5ed8d3850` | `baa9ec459a120deb19945976b4b7b8d629e0c55b970c702bef2f74704632a090` | downloaded | 1.021 |
| noisecapture | Niger.zip | 30584 | `aed35d7f0316843c44b1dd27596ee15a` | `b57ca20b3a85be3fe7e5822cb1c7e8d1c1902377f361d763291043b3d2a77ba4` | downloaded | 0.982 |
| noisecapture | Palau.zip | 29885 | `75bd809e2c70a7ebfc0350d542072d01` | `083ad224343319828d9d5359d3643c3d69add5295b788177847297bc4d31d678` | downloaded | 1.073 |
| noisecapture | Malawi.zip | 23633 | `ecdebd488e3cfcee3ce50f684be6c2fe` | `224cd6ffb79c210f1b6909d9c531f1e7fc1a3029522e570e783bf260d161390c` | downloaded | 0.986 |
| noisecapture | San Marino.zip | 21517 | `9fa35e78a973516b1d74abd0b92de30b` | `da9f6b68990f21d5fc5cf5142a5304bc3010329d594372202c216199310a51ee` | downloaded | 0.981 |
| noisecapture | Andorra.zip | 28610 | `89bead28c427a3fbe106369bdfa73366` | `935deef514d9d1dba573bf9173d7c4d9bd6893be989dc25394b8e3afef6c8a5d` | downloaded | 1.083 |
| noisecapture | Antarctica.zip | 21309 | `a4ad8143d67539cac54250f3a575a573` | `bbbd5854716747f01c29f4eb7c6542ef8684cdf90ed51d2bea49d5fea2147627` | downloaded | 1.006 |
| noisecapture | Saint Pierre and Miquelon.zip | 20458 | `243205eefa6b9866e8d0c39a2e833fa2` | `1d2f40e607033774a5b605aa6bf87c473f41a00f7133019b20367201dbb24e6c` | downloaded | 0.985 |
| noisecapture | Mauritania.zip | 15053 | `51c5242af133dcb194ed5f7e2b754905` | `83f1c3c884a2778a02f36ee9e080e4dc78f33fa80bbd9243fe1d0103678ac0e8` | downloaded | 0.983 |
| noisecapture | Kyrgyzstan.zip | 20212 | `527d3b1ef053bb289b8a6315a396183a` | `1e823a73434391a65cad60979e98f22bed76b27dde75f7cef6f4041572cc119c` | downloaded | 1.006 |
| noisecapture | Vatican City.zip | 14899 | `b9d147266bb3acd1c453d5908b172367` | `1fcf2f1c315b9d347aff1ed0eca7b50053e305137898add77fd9841f89f9db2e` | downloaded | 0.989 |
| noisecapture | Mongolia.zip | 10857 | `3b70f345f84706c9d52fe768882ea231` | `297455286bc2e05a68b65835a7808da0e259ef54ea75c4fb7c96a5b083d3937a` | downloaded | 0.83 |
| noisecapture | Belize.zip | 14204 | `8c8ccce9f4234edf9a8f2cb5b317adda` | `0d721f0c8cdf3f938c4b2069a01e8f6ed0e8ab18981fb8d1ea0ce4eef32912ce` | downloaded | 1.029 |
| noisecapture | Saint-Martin.zip | 12773 | `5bb82d13aa26f603d8e58806d18dd28f` | `d6f99ba4463b857c2ce380d8ed1963dff2e4850520c2acdf552d2a7a0e7cbb86` | downloaded | 1.153 |
| noisecapture | Northern Mariana Islands.zip | 10741 | `786c9784561bd976dc65581b487c3cc0` | `909979e87648de193f5f0a6c0bc331f12b6134446fc9f4c9d0f5f5e80b7f7f9e` | downloaded | 0.831 |
| noisecapture | Barbados.zip | 10553 | `f99644ec8702683382adebe56aff39b0` | `04c452c6f3b81d9a4da89f7fbdb430bccfb149d95e0a5898dc6e9c55d24ecdc0` | downloaded | 0.851 |
| noisecapture | Seychelles.zip | 10399 | `2b479a93ade7b25c1c6b1edad55e613f` | `adc9fb5475a78d7759e07fee03a8cd5ebb9da5ee8e873cc7bb443889daef4c55` | downloaded | 0.824 |
| noisecapture | Tonga.zip | 9590 | `a9f75813b75b4c537d0c84150705178c` | `dcc6644edf38c7d9370cfb0663680eb3f4bbd4d673ed8c7ffd49d3fc732252ab` | downloaded | 0.842 |
| noisecapture | Western Sahara.zip | 9582 | `ac26a66bbc625dc1ddb45fd970c515cb` | `41827ad159f82bca57408f9a71c8f56abc51187993d548273756afe42d58a3f4` | downloaded | 0.825 |
| noisecapture | Sierra Leone.zip | 9467 | `cf549ae981a9fca461be2ea763959392` | `bd5e17dfc89c1c4cff047057094bb21e5f546fab502c0db35ff1563ad350af1d` | downloaded | 0.831 |
| noisecapture | Mozambique.zip | 9232 | `320d4cd3255a2e81a06e3f67577fee8d` | `156367681ffad0176f7085f51e2a18524e53b849fe7231e9dc504543460803c1` | downloaded | 0.831 |
| noisecapture | Bahamas.zip | 8947 | `cb2f1c05a6a080e786bc086137c4db22` | `f5e84f6c67fc742115a0646a0f23c0adc886a7f62811a7fd3a60e6ac143045e5` | downloaded | 0.82 |
| noisecapture | Saint Kitts and Nevis.zip | 8628 | `4c85f01130078acf9ca45f4b2019824b` | `5b469768eed0917316d78bc9e5e3098e13885e9f2595ab1db2889ea3bab60a18` | downloaded | 0.869 |
| noisecapture | Sint Maarten.zip | 7503 | `b332e170bd054e521ac6b85832fbca49` | `3a4310ea32a5679987474146df28889954724f64181f8f51473076a6b0078f90` | downloaded | 0.827 |
| noisecapture | Guernsey.zip | 7093 | `a3e14c2669190ae073bda8540f4b2920` | `77df44283f3142751a066215c274beafd144c91040ebcba49f3fa83b86e94451` | downloaded | 0.882 |
| noisecapture | Nauru.zip | 6940 | `82f79077d98be0eb01240c9fea57a51f` | `dd5ab6cdf0dd7a641a285a6e8eaea0b6646e3571f0ebbca6d8ab5105e7112ac4` | downloaded | 0.837 |
| noisecapture | Gambia.zip | 5975 | `9f39edf6524286a8c72568925e4dd762` | `bd09dd152dc36cdb372fd8fe127e4aef7287d69cb4f0a685af53cc7ab56c0c44` | downloaded | 0.843 |
| noisecapture | Burundi.zip | 6682 | `19f7d5389d232efd045bcfa3f85f88ef` | `3d880aa83acb47382c8d085690739fc70830de1124c00110d574c5947597947a` | downloaded | 0.894 |
| noisecapture | Dominica.zip | 5866 | `ea7d406d906f1866d1232cd5dab08cc3` | `1e8e913906021da45d67cb4078a4d82c86f2108c8996098d884a310faf39174d` | downloaded | 0.836 |
| noisecapture | American Samoa.zip | 5545 | `57c682ee730e6bb790848a341f201d6c` | `d5572f78340f31bbd07f933d4b3f3f1b33a092b8b83046a84a1c104110a6049d` | downloaded | 0.866 |
| noisecapture | Gibraltar.zip | 5306 | `56206686ece2213729623d2b70bbe4af` | `1ea351cafff7f23d9d5fd2a60b1d42d300d6fd1cef3a9770b31863cb3957b237` | downloaded | 0.821 |
| noisecapture | Micronesia.zip | 4962 | `c25aa49081cdfb1b8ad7a5e5f6e3f37f` | `9b328558b7e0e70a1c2dfe5d10f737907fba5e99714166407694679706579a52` | downloaded | 0.93 |
| noisecapture | Tajikistan.zip | 4920 | `0371f872970488144d719a09ad789820` | `261abd62aa11ee1d07a2af96aa0fe0c05c0a7161fb0c142a4af7a41c4c6604ba` | downloaded | 0.823 |
| noisecapture | Antigua and Barbuda.zip | 4786 | `0cda1fac466baeb5b7056b2b80be51cc` | `c5cb9703a77192b862e34073f122a299afa7d4a0beb03641c57eaa2b596eb782` | downloaded | 0.905 |
| noisecapture | Turkmenistan.zip | 4820 | `ba402f85974106d856a81b4716871812` | `ca6d8308ea056178eb8f4611df6b1ba32c3b64ca4d8f61b2bb925f2906f8f0d4` | downloaded | 0.813 |
| noisecapture | Aruba.zip | 4637 | `b06a428516ed7e4d431dd0de758b00a8` | `1b5d359857d46743484dbb5bbe8b84b11515395932c8db3d82df2f68553d2731` | downloaded | 0.873 |
| noisecapture | Guinea-Bissau.zip | 4627 | `ccb6af3cf157f65c0c67e05c9ed7718b` | `047b2683eb981414717e6e59bcbca7be480366979aecdd067352812565a673e4` | downloaded | 0.845 |
| noisecapture | Equatorial Guinea.zip | 4551 | `2ee5bf072269a4d39ae345ec755afd2a` | `9a3bb4e08ddbe40a773dfc02d8a230cd8d533501b7e0ca359d87f0ad53a86b2f` | downloaded | 0.824 |
| noisecapture | Samoa.zip | 4551 | `f68d99550949c129e4dcd91657019f06` | `ab4c069eb2656f604e1209b2023da97b6bcb45429c63bb4e8b9fd682a6c8f5e7` | downloaded | 0.933 |
| noisecapture | Akrotiri and Dhekelia.zip | 4047 | `e5315b849f9f2664e9ff27204d9b5689` | `debde0d39fadf657fa8c9f63e45cd999659f2bbbdac72bc031e48bd9f52ef1f9` | downloaded | 0.821 |
| noisecapture | Fiji.zip | 4242 | `523efd9f58750229726d0d788942e0f6` | `e4793216eb03556d7f71e4fd07b9b0eab08106752bfb92a394b74581e428834e` | downloaded | 0.861 |
| noisecapture | Christmas Island.zip | 3956 | `b50e0b42100ee7accc88170977f1848d` | `6253c43825a51fcb51462cea97eddfd763d9ec020ba7f15ab9cf21dabf6d61f2` | downloaded | 0.833 |
| noisecapture | Lesotho.zip | 3942 | `cce70b0dd97c3b57773f180a93ef3c97` | `4411fd25da3b7aa74a760777a9ea8969fa2ccdfb4ebe3f514d65bf9820782f8b` | downloaded | 0.822 |
| noisecapture | Bonaire, Sint Eustatius and Saba.zip | 3749 | `af15f6c2a0e9ff1d740a26181eb05a3f` | `316b7fbc36f9c24cbc778092f0f65ae75cd5d93d0f255b759cd3165ee3680bee` | downloaded | 0.817 |
| noisecapture | Greenland.zip | 3790 | `78b266b26a14e0fdccd3cbd1b14a39b2` | `37730cf65794a79f23f6fbf4237d234b59ac65c39588ac15aec9d09876d9fb44` | downloaded | 0.824 |
| noisecapture | Cook Islands.zip | 3708 | `a48cfc0ed91793fde2e92051431850b9` | `52f270d7b86e5c435c79d09f19db7657567b8a5ec3fb6c4c88345a4043059184` | downloaded | 0.826 |
| noisecapture | British Virgin Islands.zip | 3432 | `72ee442de103602bd37ba348b87b19a7` | `93f8f3c51d26d700c26da2ca1e2f8cbbe22716116fa7f7e41274407fe0302713` | downloaded | 0.828 |
| noisecapture | Faroe Islands.zip | 3382 | `9207d80056f87b12b5bdba6a3385f291` | `3d10ddbed3b576e7085825803713e76299c398ab76c1255b6b296b6f91d77d24` | downloaded | 0.83 |
| noisecapture | South Sudan.zip | 3385 | `0f7f04d26e20554a95dc9eb4baff38db` | `ba5ddc5286aabb413195c0a920af4829b50e59b2bfb495068da05d082ae92b0d` | downloaded | 0.825 |
| noisecapture | Saint Lucia.zip | 3229 | `4861763c8eb6b742199452ec23603736` | `51f58707afca229eb2832284acfb8699745f7873635159cf3c8d5824ee1d8c3b` | downloaded | 0.822 |
| noisecapture | Turks and Caicos Islands.zip | 3194 | `9413c0a987f193a5da0953a6b3a79df6` | `3345497300a23d2936d39de5fb3a63b69f1084d412859b1325280fc90bd677da` | downloaded | 0.823 |

Per-file URL, license, official checksum comparison, ETag, and error text are in `data/manifests/download_manifest.json`.
