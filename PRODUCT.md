# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: hackathon judges evaluating the project in a live demo, on a desktop browser at a venue. They need to grasp in seconds what place is shown, what the tool will eventually do, and that the team is honest about what the data can and cannot say.

The story's subjects, not the demo's operators: residents of Bay, Pila, Victoria and Santa Cruz, and municipal DRRM / LGU staff planning drainage and evacuation. Their needs shape terminology and honesty constraints, not the current information density.

## Product Purpose

**MATA: Tanaw** — *Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters*. (*mata* = eye, *tanaw* = view / gaze across a distance.)

Goal: a SAR-based decision-support web app. Using multi-temporal Sentinel-1 backscatter change detection, it replays how typhoon floods spread and receded in Philippine river basins and maps how long each barangay stayed underwater, with uncertainty ranges. Exposure indices and resident photo validation help LGUs and DRRM offices prioritise drainage, evacuation and recovery. Research basis: `Flood-Rewind-What-the-Typhoon-Left-Behind.pdf`.

Cadence: Sentinel-1 is not daily. Over the selected Laguna area, descending track 32 passes about 05:47 Philippine time and ascending track 142 about 18:05. Each track uses its own dry-season reference from the replay window; four-year seasonal normalization is deferred.

Current phase: map Laguna's 30 municipalities and 682 COD-AB barangays. Process primary Sentinel-1 observations for **Bay, Pila, Victoria and Santa Cruz** over 2024-11-15 to 2026-11-15. The current published preview covers Bay only (84 descending passes); the four-municipality, two-track run is in progress. Other municipalities are unknown, not dry.

Success for this phase: a judge identifies the four focus municipalities, steps through real pass dates, opens a barangay and sees observed flood evidence and unknown coverage without implying daily or continuous observation.

## Positioning

Time and duration of flooding, with uncertainty built into the display, at barangay level — not a single extent map. The viewer refuses to show anything the satellite record does not support: observed dates only, ranges not point values, missing data never zero-filled.

## Operating Context

- Live hackathon demo on desktop, venue internet and GPU unknown; mobile must remain usable (bottom sheet) but is secondary.
- Static hosting, no backend. MapLibre GL JS with tilted perspective (isometric-inspired, not true isometric).
- Data sources requiring visible attribution: OpenStreetMap / Protomaps, Copernicus GLO-30, NAMRIA and PSA via OCHA COD-AB (barangay geometry).

## Capabilities and Constraints

- In scope now: observed-pass replay and Sentinel-1 open-water flood indications for the four focus municipalities; GLO-30 terrain, OSM buildings, COD-AB boundaries and contextual Laguna de Bay level.
- Deferred: four-year normalization, secondary satellite opinions, duration estimates, rainfall, exposure indices, photo upload, modelled frames and storm attribution.
- Terminology: barangay, PSGC, pass, flood signal, below threshold, unknown and low confidence (water on cropland or wetland, often paddies).
- Undecided: exposure index definition, boundary vintage for historical joins.

## Brand Commitments

- Name: **MATA: Tanaw**, expansion *Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters*. Repo name `masaSARap` is internal.
- UI language: English.
- Voice: plain-language, honest about limits; prefer "observed on these dates" over implying continuous monitoring.

## Evidence on Hand

- Research brief PDF and architecture plan in repo root.
- 682 COD-AB v03 barangay polygons across Laguna, including 67 in the four focus municipalities (`public/data/PROVENANCE.md`).
- Published primary-source flood frames and per-barangay records cover Bay only so far; the other three are being processed. No photos, statistics or testimonials may be fabricated or implied.

## Product Principles

1. Never show what wasn't observed. Empty means unknown, not zero.
2. The place comes first: Bay must be recognisable before anything else is explained.
3. Honesty is a feature to demonstrate, not a footnote.
4. Barangay is the unit people act on.

## Accessibility & Inclusion

Keyboard-accessible barangay list as alternative to map hit-testing; visible focus; screen-reader names; reduced motion for camera transitions; no reliance on color alone; color-blind-safe palette for future flood layers.
