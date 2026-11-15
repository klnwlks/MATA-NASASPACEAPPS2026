# MATA: Tanaw

**Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters**

MATA: Tanaw is an interactive satellite-radar replay for exploring possible floodwater around Laguna de Bay, Philippines. It brings observations together at barangay level to support conversations about drainage, evacuation and recovery.

Live app: https://matatanaw.vercel.app/

Built by Team Masasarap for the 2026 NASA Space Apps Challenge, [Dancing with the SARs](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/).

## What it shows

- A 3D map of Laguna's 30 municipalities and 682 barangays, with searchable boundaries, terrain and building context.
- A replay of 136 Sentinel-1 passes from November 2024 to November 2026 for Bay, Pila, Santa Cruz and Victoria. Observations are irregular, not daily.
- Per-barangay flood signals and secondary evidence from NASA OPERA DSWx-S1, ASF HyP3 coherence and NASA–ISRO NISAR where available.
- Laguna de Bay water-level observations from DAHITI, shown as context.

**Not an official hazard map.** Flood indications are preliminary and are not ground-validated. Radar can miss water beneath buildings or vegetation, and agricultural water can resemble flooding. Missing coverage is unknown, not dry. Duration estimates, exposure indices and resident photo validation are not yet available.

## How it works

Flooding is not just a question of **where** water appeared, but **how it changed over time**. MATA: Tanaw brings satellite observations together on a map and timeline, letting users step through radar passes to explore where flooding may have spread, persisted or receded across barangays.

Each source adds a different piece of the picture. Sentinel-1 sees through clouds and reveals changes in open water. NASA's OPERA water maps provide another reading of Sentinel-1; ASF HyP3 coherence highlights changes in built-up areas; and NASA–ISRO NISAR adds a different radar perspective where available. Comparing these signals with earlier observations helps reveal patterns that a single layer could miss.

The timeline shows observed passes, not a continuous record. Buildings, vegetation and agricultural water can obscure or mimic flooding, and gaps between observations remain unknown.

## Tech stack

- React, Vite and Tailwind CSS for the web interface.
- MapLibre GL JS and Three.js for the interactive map and 3D layers.
- Python, NumPy, SciPy, Rasterio and Shapely for geospatial processing.
- Remotion for the demo video.

## Run locally

Requirements: Node.js and npm.

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. `npm run build` creates the production build; `npm run preview` serves it locally.

## Data, references and licenses

The main sources include Copernicus Sentinel-1, NASA OPERA DSWx-S1, NASA–ISRO NISAR, ASF HyP3, Copernicus DEM GLO-30, ESA WorldCover, EOX Sentinel-2 cloudless, OpenStreetMap, OCHA COD-AB and DAHITI. See [project references](public/references.txt) for sources, tools, research and demo-video credits, and [data provenance](public/data/PROVENANCE.md) for versions, transformations and limitations.

EOX Sentinel-2 cloudless imagery is licensed CC BY-NC-SA 4.0, restricting use to non-commercial purposes. The team must verify undocumented asset permissions and add any other resources used before submitting.

Code was developed with AI assistance.

## Team

Lukas Bebis, Angelica Saavedra, Jed Cabacang, Dave Caidic, Jericon Esguerra and Anthony Espina.
