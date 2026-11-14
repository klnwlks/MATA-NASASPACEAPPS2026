# Data provenance

Retrieved 2026-11-14. Regenerate with the scripts in `scripts/` (see each header).

| File | Source | Version / date | Licence | Transformation |
|---|---|---|---|---|
| `barangays.geojson` | OCHA COD-AB Philippines (PSA, NAMRIA), `phl_admin4` layer, dataset `cod-ab-phl` on HDX | v03, valid 2025-02-13 | CC BY-IGO | Filtered to PSGC prefix `0403411`, PSGC normalised to 10-char string, geometry simplified at 1e-5 deg (about 1 m) with topology kept |
| `terrain/` | Copernicus DEM GLO-30 public COG `Copernicus_DSM_COG_10_N14_00_E121_00_DEM` (AWS Open Data, no account) | 2021 release | Copernicus DEM licence; credit "Contains modified Copernicus DEM GLO-30 data" | Bilinear warp to Web Mercator tiles z8 to z12, Terrarium encoding, nodata to 0 m. Surface model, not bare earth; about 30 m cells; heights are EGM2008 orthometric metres |
| `losbanos.pmtiles` | Protomaps basemap build `20261113.pmtiles` (v4.15.2), derived from OpenStreetMap | build 2026-11-13 | ODbL, credit "OpenStreetMap contributors" | `pmtiles extract` with bbox 121.091,14.03,121.347,14.278, z0 to z15 |
| `trees.geojson` | `losbanos.pmtiles` above (`pois` kind `tree`, `landuse` polygons); elevation from `terrain/` z12 | build 2026-11-13 | ODbL, credit "OpenStreetMap contributors" | `scripts/trees.py`: feature 1 is 3,606 OSM tree points. Feature 0 is 131,841 seeded random points inside wood, forest, nature reserve, park and garden polygons within the municipality plus 300 m. These are decorative, not observed trees. Each point carries a bilinear Terrarium elevation sample (m) |

## Known limits

- Terrain AOI is the barangay bounds plus 0.08 deg, kept inside the single GLO-30 tile N14 E121.
- Of 16,267 building features sampled at z15 across the municipality, 1,605 (about 10 %) carry a `height`. The rest get a fixed schematic height in the app.
- Barangay 0403411009 does not exist in the source; 14 barangays are listed, matching PSA.
- Boundaries are reference geometry, not a legal determination.
