# Data provenance

Retrieved 2026-11-15 (area moved from Los Baños to Bay, Laguna). Regenerate with the scripts in `scripts/` (see each header).

| File | Source | Version / date | Licence | Transformation |
|---|---|---|---|---|
| `barangays.geojson` | OCHA COD-AB Philippines (PSA, NAMRIA), `phl_admin4` layer, dataset `cod-ab-phl` on HDX | v03, valid 2025-02-13 | CC BY-IGO | Filtered to PSGC prefix `0403402` (Bay), PSGC normalised to 10-char string, geometry simplified at 1e-5 deg (about 1 m) with topology kept |
| `terrain/` | Copernicus DEM GLO-30 public COG `Copernicus_DSM_COG_10_N14_00_E121_00_DEM` (AWS Open Data, no account) | 2021 release | Copernicus DEM licence; credit "Contains modified Copernicus DEM GLO-30 data" | Bilinear warp to Web Mercator tiles z8 to z12, Terrarium encoding, nodata to 0 m. Surface model, not bare earth; about 30 m cells; heights are EGM2008 orthometric metres |
| `basemap.pmtiles` | Protomaps basemap build `20261113.pmtiles` (v4.15.2), derived from OpenStreetMap | build 2026-11-13 | ODbL, credit "OpenStreetMap contributors" | `pmtiles extract` (go-pmtiles v1.31.2) with bbox 121.125,14.002,121.382,14.279, z0 to z15 |
| `trees.geojson` | `basemap.pmtiles` above (`pois` kind `tree`, `landuse` polygons); elevation from `terrain/` z12 | build 2026-11-13 | ODbL, credit "OpenStreetMap contributors" | `scripts/trees.py`: feature 1 is 2,068 OSM tree points. Feature 0 is 27,266 seeded random points inside wood, forest, nature reserve, park and garden polygons within the municipality plus 300 m. These are decorative, not observed trees. Each point carries a bilinear Terrarium elevation sample (m) |

## Known limits

- Terrain AOI is the barangay bounds plus 0.08 deg, kept inside the single GLO-30 tile N14 E121.
- Of 1,570 building features sampled at z15 inside Bay, 243 (about 15 %) carry a `height`. The rest get a fixed schematic height in the app. OSM building coverage in Bay is sparse; missing footprints are unknown, not empty land.
- Barangays 0403402007 and 0403402008 do not exist in the source; 15 barangays are listed. Not yet checked against the PSA list.
- Boundaries are reference geometry, not a legal determination.
