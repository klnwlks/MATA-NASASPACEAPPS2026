# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: hackathon judges evaluating the project in a live demo, on a desktop browser at a venue. They need to grasp in seconds what place is shown, what the tool will eventually do, and that the team is honest about what the data can and cannot say.

The story's subjects, not the demo's operators: Bay residents in low-lying lakeshore and paddy barangays, municipal DRRM / LGU staff planning drainage and evacuation. Their needs shape terminology and honesty constraints, not the current information density.

## Product Purpose

**MATA: Tanaw** — *Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters*. (*mata* = eye, *tanaw* = view / gaze across a distance.)

Goal: a SAR-based decision-support web app. Using multi-temporal Sentinel-1 backscatter change detection, it replays how typhoon floods spread and receded in Philippine river basins and maps how long each barangay stayed underwater, with uncertainty ranges. Exposure indices and resident photo validation help LGUs and DRRM offices prioritise drainage, evacuation and recovery. Research basis: `Flood-Rewind-What-the-Typhoon-Left-Behind.pdf`.

Cadence: Sentinel-1 is not daily. Bay is covered by one descending track (relative orbit 32, about 05:47 Philippine time): every 12 days until mid-2025 (S1A alone), then mostly every 6 days (S1A+S1C, later S1C+S1D). The ascending track 142 exists from April 2025 but is not mixed in: a second viewing geometry needs its own reference and adds false changes.

Current phase: **Bay, Laguna** (PSGC `0403402000`, 15 barangays), the last two years of track-32 passes (2024-11-15 to 2026-11-15). 3D stage (GLO-30 terrain, OSM buildings, COD-AB barangays) plus a replay of every observed pass, per-barangay flooded runs as "between X and Y days" ranges, municipality-wide flood runs, per-pass second opinions (NASA OPERA DSWx-S1; NISAR L-band from June 2026) and the Laguna de Bay level from altimetry (DAHITI). Storms are not named by the app; runs are dated only.

Success for this phase: a judge recognises Bay on Laguna de Bay, steps through real pass dates, opens a barangay and reads a duration range bounded by real passes, and sees where the record is unknown.

## Positioning

Time and duration of flooding, with uncertainty built into the display, at barangay level — not a single extent map. The viewer refuses to show anything the satellite record does not support: observed dates only, ranges not point values, missing data never zero-filled.

## Operating Context

- Live hackathon demo on desktop, venue internet and GPU unknown; mobile must remain usable (bottom sheet) but is secondary.
- Static hosting, no backend. MapLibre GL JS with tilted perspective (isometric-inspired, not true isometric).
- Data sources requiring visible attribution: OpenStreetMap / Protomaps, Copernicus GLO-30, NAMRIA and PSA via OCHA COD-AB (barangay geometry).

## Capabilities and Constraints

- In scope now: everything above plus the observed-pass replay, flood overlay per pass, per-barangay flood area (high and low confidence), duration ranges, second opinions and lake level.
- Out of scope now: rainfall, exposure indices, photo upload, modelled frames between passes, storm attribution.
- Terminology: barangay, PSGC, pass, observed vs modeled vs unknown, low confidence (water on cropland or wetland, often paddies), "flooded for between X and Y days".
- Undecided: exposure index definition, boundary vintage for historical joins, whether to add track 142.

## Brand Commitments

- Name: **MATA: Tanaw**, expansion *Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters*. Repo name `masaSARap` is internal.
- UI language: English.
- Voice: plain-language, honest about limits; prefer "observed on these dates" over implying continuous monitoring.

## Evidence on Hand

- Research brief PDF and architecture plan in repo root.
- 15 COD-AB v03 barangay polygons for Bay, PSGC municipality code `0403402000` (`public/data/PROVENANCE.md`).
- Flood frames and per-barangay records derived from Sentinel-1 RTC (`scripts/floods.py`, `scripts/flood_summary.py`). No photos, statistics or testimonials exist. None may be fabricated or implied.

## Product Principles

1. Never show what wasn't observed. Empty means unknown, not zero.
2. The place comes first: Bay must be recognisable before anything else is explained.
3. Honesty is a feature to demonstrate, not a footnote.
4. Barangay is the unit people act on.

## Accessibility & Inclusion

Keyboard-accessible barangay list as alternative to map hit-testing; visible focus; screen-reader names; reduced motion for camera transitions; no reliance on color alone; color-blind-safe palette for future flood layers.
