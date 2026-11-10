# Dataset quality report

Generated at 2026-11-10T02:08:43.891523+00:00 by `scripts/preprocess_datasets.py`.

Every count in this file is taken from the preprocess summary written by that run. Upstream web pages are not used as row counts.

Command: `scripts/preprocess_datasets.py --dataset all --data-dir data --resume`

No YJMob latitude or longitude column is created. NoiseCapture `noise_level`, `laeq`, `la50`, and `lden` stay in separate accumulators. An arithmetic mean of decibel numbers is never stored as an energy-equivalent level.

## YJMob100K

Physical trajectory columns are whatever the gzip header contains. The released files use `uid,d,t,x,y`. `d` is the day index and `t` is the timeslot index named by the Zenodo description; this script does not rename them and does not turn them into clock times or geographic coordinates.

### yjmob100k-dataset1.csv.gz

- Rows: 111535175
- Users: 100000
- Distinct day values: 75 (min 0, max 74)
- Distinct timeslot values: 48 (min 0, max 47)
- x range: 1 to 200; y range: 1 to 200
- Null uid/day/timeslot/x/y: 0, 0, 0, 0, 0
- Rows with x=0 or y=0: 0
- Rows outside the 1..200 grid mentioned in the Zenodo challenge text: 0
- Unique (user, day, timeslot) keys: 111535175
- Duplicate extra rows inside those keys: 0
- User-days with at least one row: 7147619
- Absent timeslots inside those user-days, using the global observed timeslot set: 231550537
- Absent combinations of the observed uid, day, and timeslot sets: 248464825
- Missing day indices inside min..max: 0
- Missing timeslot indices inside min..max: 0

Subsets keep every stored row for the lowest uid values. They are not a dense 75 by 48 grid.

| users requested | users written | rows | day min | day max | columns |
| ---: | ---: | ---: | ---: | ---: | --- |
| 10 | 10 | 15718 | 0 | 74 | `uid,d,t,x,y` |
| 100 | 100 | 134306 | 0 | 74 | `uid,d,t,x,y` |
| 1000 | 1000 | 1228051 | 0 | 74 | `uid,d,t,x,y` |

### yjmob100k-dataset2.csv.gz

- Rows: 29389749
- Users: 25000
- Distinct day values: 75 (min 0, max 74)
- Distinct timeslot values: 48 (min 0, max 47)
- x range: 1 to 200; y range: 1 to 200
- Null uid/day/timeslot/x/y: 0, 0, 0, 0, 0
- Rows with x=0 or y=0: 0
- Rows outside the 1..200 grid mentioned in the Zenodo challenge text: 0
- Unique (user, day, timeslot) keys: 29389749
- Duplicate extra rows inside those keys: 0
- User-days with at least one row: 1774138
- Absent timeslots inside those user-days, using the global observed timeslot set: 55768875
- Absent combinations of the observed uid, day, and timeslot sets: 60610251
- Missing day indices inside min..max: 0
- Missing timeslot indices inside min..max: 0

Subsets keep every stored row for the lowest uid values. They are not a dense 75 by 48 grid.

| users requested | users written | rows | day min | day max | columns |
| ---: | ---: | ---: | ---: | ---: | --- |
| 10 | 10 | 16256 | 0 | 74 | `uid,d,t,x,y` |
| 100 | 100 | 136175 | 0 | 74 | `uid,d,t,x,y` |
| 1000 | 1000 | 1261183 | 0 | 74 | `uid,d,t,x,y` |

Uid overlap between `yjmob100k-dataset1.csv.gz` and `yjmob100k-dataset2.csv.gz`: 25000.

POI category file `POI_datacategories.csv` nonempty lines: 85. The file is a list of category names, one per line, with no header and no coordinates.

Cell POI file `cell_POIcat.csv.gz` rows: 221159, columns: 4, header mode: header row.

## GeoLife

- Users: 182
- Trajectory files: 18670
- Raw points after the 6-line header: 24876978
- Accepted points: 24173770
- Rejected points: 703208
- raw == accepted + rejected: True
- Rejected reasons: `{'impossible_jump': 209814, 'duplicate_timestamp': 493393, 'bad_coordinate': 1}`
- Accepted distance, haversine sum: 7.02954e+08 m (702954 km)
- Distinct grid cells 250/500/1000 m: `{'250': 345712, '500': 184473, '1000': 96923}` truncated=`{'250': False, '500': False, '1000': False}`
- Header lines containing feet: 18670 files; without feet: 0
- Header lines containing WGS: 18670 files; without WGS: 0
- Parsed points whose altitude field is -777: 55484. The point is kept. This sentinel is counted because the user-guide text, when recovered, describes -777 as an invalid altitude.
- Timestamp timezone label: GMT
- Timezone evidence excerpt: `, location and trajectory. Invited paper, in IEEE Data Engineering Bulletin. 33, 2, 2010, pp. 32-40. 4. Data Format 4.1. Trajectory file Every single foldmat. Each PLT file contains a single trajectory and is named by its starting time. To avoid potential confusion of time zone, we use GMT in the date/time property of each point, which is different from our previous release. PLT format: Points are described in following lines, one for each line. Field 1: Latitude in decimal degrees. Field 2: Longitude in decimal degrees. Field 3: All set to 0 for this d`
- `labels.txt` files left unread: 69
- Haversine self-check, 0 m and one degree of latitude: `{'zero_distance_m': 0.0, 'one_degree_latitude_m': 111195.0802335329}`

Rules applied:

- header_lines_skipped: 6
- coordinate_system: WGS84
- distance: haversine, Earth radius 6371008.8 m
- impossible_jump: After the last accepted point, reject the candidate when delta_t<=0 and separation>1 m, or when delta_t>0 and speed>1000 km/h.
- duplicate_timestamp: Reject the candidate when delta_t<=0 and separation<=1 m.
- null_island: Reject latitude==0 and longitude==0 before the jump test.
- bad_coordinate: Reject latitude outside [-90, 90] or longitude outside [-180, 180].
- grids: Equirectangular bins at 250, 500, and 1000 m. grid_y = floor(latitude * 111132.92 / meters). grid_x = floor(longitude * 111132.92 * cos(latitude) / meters). These bins are not YJMob indices and are not a projected CRS.

First parsed `.plt` header, the six lines that are skipped:

```
Geolife trajectory
WGS 84
Altitude is in Feet
Reserved 3
0,2,255,My Track,0,0,2,8421376
0
```

## NoiseCapture

- Archives parsed successfully: 227 of 227
- Point features: 158222603
- Track features: 511161
- Area features: 2395782
- Parse errors: 0
- Invalid coordinates excluded from the bbox only: 0
- Bbox [min lon, min lat, max lon, max lat]: `[-175.215739, -82.2674535847421, 178.4422188, 78.7266908905091]`

points.noise_level, tracks.noise_level, areas.laeq, areas.la50, and areas.lden are accumulated separately. leq_profile arrays are stored as JSON text and are not reduced to a mean. The energy mean is 10*log10(mean(10^(L/10))). The arithmetic mean is the mean of the decibel numbers. Track duration-weighted energy mean uses time_length as the weight and is separate from the unweighted energy mean.

| indicator | count | nulls | zeros | overflow excluded | min | max | energy mean dB | arithmetic mean dB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| points.noise_level | 158222603 | 0 | 3240060 | 0 | -56.7613 | 150 | 94.704 | 59.0285 |
| tracks.noise_level | 511161 | 0 | 0 | 0 | 0.15 | 148.65 | 100.524 | 63.7664 |
| areas.la50 | 2395782 | 0 | 21776 | 0 | -27.7399 | 147.359 | 93.1673 | 69.4544 |
| areas.laeq | 2395782 | 0 | 18320 | 0 | -27.7399 | 147.359 | 93.7645 | 71.5615 |
| areas.lden | 2395782 | 0 | 2395782 | 0 | 0 | 0 | 0 | 0 |

Track `noise_level` duration-weighted energy mean, weights `time_length`: 96.3487 dB over 511161 tracks with positive duration. Tracks missing a usable weight: 0.

Tracks whose point-level energy mean was compared with the track `noise_level`: 507292. Mean absolute difference: 0.846956 dB. Max absolute difference: 59.0442 dB.

Area features with both la50 and laeq: 2395782. Pairs equal within 1e-6: 1093789.

Largest point files:

| archive | member | point features |
| --- | --- | ---: |
| Greece.zip | Greece_Macedonia and Thrace_Central Macedonia.points.geojson | 11671419 |
| Slovenia.zip | Slovenia_Osrednjeslovenska_Ljubljana.points.geojson | 4694806 |
| France.zip | France_Rhône-Alpes_Rhône.points.geojson | 3097729 |
| United States.zip | United States_California_Los Angeles.points.geojson | 2665596 |
| France.zip | France_Île-de-France_Paris.points.geojson | 2508800 |
| France.zip | France_Pays de la Loire_Loire-Atlantique.points.geojson | 2098157 |
| Croatia.zip | Croatia_Grad Zagreb_Zagreb.points.geojson | 1691400 |
| Malaysia.zip | Malaysia_Kuala Lumpur_Kuala Lumpur.points.geojson | 1667579 |
| France.zip | France_Île-de-France_Hauts-de-Seine.points.geojson | 1415711 |
| United Kingdom.zip | United Kingdom_England_Suffolk.points.geojson | 1403045 |
| Norway.zip | Norway_Sør-Trøndelag_Trondheim.points.geojson | 1303040 |
| France.zip | France_Bretagne_Morbihan.points.geojson | 1199477 |
| Spain.zip | Spain_Comunidad de Madrid_Madrid.points.geojson | 1156867 |
| United States.zip | United States_Arizona_Maricopa.points.geojson | 1069341 |
| France.zip | France_Alsace_Bas-Rhin.points.geojson | 1022102 |
| France.zip | France_Île-de-France_Seine-Saint-Denis.points.geojson | 1000655 |
| Ecuador.zip | Ecuador_Imbabura_Ibarra.points.geojson | 997724 |
| United States.zip | United States_Georgia_Decatur.points.geojson | 990764 |
| France.zip | France_Aquitaine_Gironde.points.geojson | 956854 |
| Austria.zip | Austria_Wien_Wien.points.geojson | 949395 |
| France.zip | France_Provence-Alpes-Côte d'Azur_Bouches-du-Rhône.points.geojson | 937783 |
| France.zip | France_Pays de la Loire_Vendée.points.geojson | 921742 |
| United States.zip | United States_California_San Bernardino.points.geojson | 896429 |
| Germany.zip | Germany_Berlin_Berlin.points.geojson | 896069 |
| France.zip | France_Île-de-France_Val-de-Marne.points.geojson | 857567 |
| Canada.zip | Canada_British Columbia_Fraser Valley.points.geojson | 819729 |
| United States.zip | United States_California_Sacramento.points.geojson | 815315 |
| Colombia.zip | Colombia_Antioquia_Medellín.points.geojson | 792407 |
| United States.zip | United States_Texas_Harris.points.geojson | 717511 |
| France.zip | France_Île-de-France_Essonne.points.geojson | 671182 |
| France.zip | France_Nord-Pas-de-Calais_Nord.points.geojson | 671102 |
| United States.zip | United States_New Mexico_Bernalillo.points.geojson | 647830 |
| Canada.zip | Canada_Ontario_Frontenac.points.geojson | 640956 |
| United States.zip | United States_Texas_Bexar.points.geojson | 596054 |
| United States.zip | United States_Texas_Tarrant.points.geojson | 566103 |
| United Kingdom.zip | United Kingdom_England_Southwark.points.geojson | 564218 |
| United States.zip | United States_California_Kern.points.geojson | 562206 |
| United States.zip | United States_Florida_Polk.points.geojson | 537964 |
| Germany.zip | Germany_Baden-Württemberg_Stuttgart.points.geojson | 517168 |
| Germany.zip | Germany_Nordrhein-Westfalen_Düsseldorf.points.geojson | 514373 |

Recorded archive failures:

- `http-dump-index` status `failed` error `HTTP 200 from http://data.noise-planet.org/dump/ returned no .zip links. title='Metabase' content_type='text/html; charset=UTF-8' server='Jetty(9.2.z-SNAPSHOT)' excerpt='<!DOCTYPE html>\n<html lang="en">\n    <head>\n        <meta charset="utf-8" />\n        <meta http-equiv="X-UA-Compatible" content="IE=edge" />\n        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, minimal-ui" />\n        <meta name="apple-mobile-web-app-capable" content="yes" />\n        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />\n\n        \n\n        <title>Metabase</title>\n\n        <base href="/" />\n\n     '`

Machine-readable copy: `data/reports/preprocess_summary.json`.
