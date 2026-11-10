# Dataset licenses

Generated at 2026-11-10T01:45:57.404931+00:00 by `scripts/download_datasets.py`.

This note records the license statements returned by the upstream pages and records. It is not a legal opinion. Redistribution of the raw archives is not part of this repository; `data/raw/` is gitignored.

## YJMob100K

- Record: https://zenodo.org/records/10836269
- API: https://zenodo.org/api/records/10836269
- DOI: `10.5281/zenodo.10836269`
- Title: YJMob100K: City-Scale and Longitudinal Dataset of Anonymized Human Mobility Trajectories
- Zenodo `metadata.license.id`: `cc-by-4.0`
- Zenodo access right: `open`
- When `license.id` is `cc-by-4.0`, the license URL used here is https://creativecommons.org/licenses/by/4.0/.
- Official file checksum algorithms present on the record: `['md5']`
- Local SHA-256 values are not Zenodo checksums. The manifest marks an official MD5 as a match only when the locally computed MD5 equals the Zenodo checksum field.

The Zenodo description names the Scientific Data paper Yabe et al. 2024, DOI `10.1038/s41597-024-03237-9`, as the data descriptor. This repository does not copy that paper.

## GeoLife GPS Trajectories

- Page: https://www.microsoft.com/en-us/download/details.aspx?id=52367
- HTTP status: `200`
- Title: GeoLife GPS Trajectories
- Page error field: ``
- The fetched details text contains the word license: `False`
- The file entry parsed from the page has a name, URL, size, version, and publication time. It has no checksum field.
- Any license statement found inside the zip is added by preprocessing when a readable text file contains one. Until that scan runs, no in-zip license is claimed.

Microsoft’s own page description is stored in the manifest under `sources.geolife`. That description is Microsoft’s account of the collection. Counts used in the quality report come from parsing the zip, not from that paragraph.

## NoiseCapture

- Data page: https://noise-planet.org/noisecapture_data.html
- Exploit page: https://noise-planet.org/noisecapture_exploit_data.html
- The data page links the dump and the Open Database License at https://opendatacommons.org/licenses/odbl/.
- The exploit page also links `https://data.noise-planet.org/dump/` and the ODbL.
- `http://data.noise-planet.org/dump/` is the URL printed on the data page. The result of requesting it is recorded as its own manifest entry and is not treated as a successful archive listing unless the body contains zip links.
- Each country zip’s `README.html` is the in-archive license statement. Preprocessing records the README hash and whether the ODbL wording is present. Raw geojson is not committed.

NoiseCapture indicators are not relicensed or redefined here. `noise_level`, `laeq`, `la50`, and `lden` stay separate fields because the README and the files do not define them as one indicator.

<!-- IN_ARCHIVE_NOTES_START -->
## In-archive notes from this preprocess run

GeoLife non-`.plt` members inspected: 1.
- `Geolife Trajectories 1.3/User Guide-1.3.pdf` bytes 498597
  - printable-string hit: `: Microsoft Research Asia, Tower 2, No. 5 Danling Street, Haidian District, Beijing, P.R. China 100080 6. Release history Version 1.3 (released 2012/08/01) Version 1.2 (released 2011/10/31) Version 1.1 (released 2011/07/25) Version 1.0 (released 2010/09/30) 7. Microsoft Research License Agreement Non-Commercial Use Only << GeoLife GPS Trajectories>> This Microsoft Research License Agreement, including all exhibits ("MSR-LA") is a legal agreement between you and Microsoft Corporation (Microsoft or we) for the software or data identified above, which`
  - printable-string hit: `0 6. Release history Version 1.3 (released 2012/08/01) Version 1.2 (released 2011/10/31) Version 1.1 (released 2011/07/25) Version 1.0 (released 2010/09/30) 7. Microsoft Research License Agreement Non-Commercial Use Only << GeoLife GPS Trajectories>> This Microsoft Research License Agreement, including all exhibits ("MSR-LA") is a legal agreement between you and Microsoft Corporation (Microsoft or we) for the software or data identified above, which may include source code, and any associated materials, text or speech files, associated media and "on`
  - printable-string hit: `h Asia, Tower 2, No. 5 Danling Street, Haidian District, Beijing, P.R. China 100080 6. Release history Version 1.3 (released 2012/08/01) Version 1.2 (released 2011/10/31) Version 1.1 (released 2011/07/25) Version 1.0 (released 2010/09/30) 7. Microsoft Research License Agreement Non-Commercial Use Only << GeoLife GPS Trajectories>> This Microsoft Research License Agreement, including all exhibits ("MSR-LA") is a legal agreement between you and Microsoft Corporation (Microsoft or we) for the software or data identified above, which may include source`
  - printable-string hit: `you agree to be bound by the terms of this MSR-LA. If you do not agree, do not install copy or use the Software. The Software is protected by copyright and other intellectual property laws and is licensed, not sold. SCOPE OF RIGHTS: You may use this Software for any non-commercial purpose, subject to the restrictions in this MSR-LA. Some purposes which can be non-commercial are teaching, academic research, public demonstrations and personal experimentation. You may not distribute this Software or any derivative works in any form. In return,`
  - printable-string hit: `r use the Software. The Software is protected by copyright and other intellectual property laws and is licensed, not sold. SCOPE OF RIGHTS: You may use this Software for any non-commercial purpose, subject to the restrictions in this MSR-LA. Some purposes which can be non-commercial are teaching, academic research, public demonstrations and personal experimentation. You may not distribute this Software or any derivative works in any form. In return, we simply require that you agree: 1. That you will not remove any copyright or other notices`
  - printable-string hit: `, location and trajectory. Invited paper, in IEEE Data Engineering Bulletin. 33, 2, 2010, pp. 32-40. 4. Data Format 4.1. Trajectory file Every single foldmat. Each PLT file contains a single trajectory and is named by its starting time. To avoid potential confusion of time zone, we use GMT in the date/time property of each point, which is different from our previous release. PLT format: Points are described in following lines, one for each line. Field 1: Latitude in decimal degrees. Field 2: Longitude in decimal degrees. Field 3: All set to 0 for this d`

NoiseCapture `README.html` SHA-256 counts:
- `af66aacb27cb642ddf2de580308875cd8eed7153c3e82c822c4a9687c3f2b6e3`: 227 archives
Archives whose README mentions the ODbL: 227. Archives whose README contains the text `lden`: 0.
A README that does not define `lden` is why area `lden` stays separate from `laeq` even when both are numeric.
<!-- IN_ARCHIVE_NOTES_END -->

## Recorded HTTP dump error

```
HTTP 200 from http://data.noise-planet.org/dump/ returned no .zip links. title='Metabase' content_type='text/html; charset=UTF-8' server='Jetty(9.2.z-SNAPSHOT)' excerpt='<!DOCTYPE html>\n<html lang="en">\n    <head>\n        <meta charset="utf-8" />\n        <meta http-equiv="X-UA-Compatible" content="IE=edge" />\n        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, minimal-ui" />\n        <meta name="apple-mobile-web-app-capable" content="yes" />\n        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />\n\n        \n\n        <title>Metabase</title>\n\n        <base href="/" />\n\n     '
```
