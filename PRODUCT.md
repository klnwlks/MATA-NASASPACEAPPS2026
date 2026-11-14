# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: hackathon judges evaluating the project in a live demo, on a desktop browser at a venue. They need to grasp in seconds what place is shown, what the tool will eventually do, and that the team is honest about what the data can and cannot say.

The story's subjects, not the demo's operators: Los Baños residents in low-lying barangays, municipal DRRM / LGU staff planning drainage and evacuation. Their needs shape terminology and honesty constraints, not the current information density.

## Product Purpose

**MATA: Tanaw** — *Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters*. (*mata* = eye, *tanaw* = view / gaze across a distance.)

Long-term goal: replay how typhoon floodwater spread and receded using SAR (Sentinel-1) observations, show how long water stayed per barangay as a range, and validate against resident photos. Research basis: `Flood-Rewind-What-the-Typhoon-Left-Behind.pdf`.

Current phase (see `MAP-VIEWER-ARCHITECTURE.md`): a 3D geographic stage of **Los Baños, Laguna** only — real terrain (Copernicus GLO-30), extruded OSM building footprints, selectable barangay boundaries with name and 10-digit PSGC, a sidebar, and a visibly disabled storm timeline. No water, flood, or storm data is rendered in this phase.

Success for this phase: a judge recognizes Los Baños, selects a barangay, reads its real identifiers, and understands that storm replay is coming and not faked.

## Positioning

Time and duration of flooding, with uncertainty built into the display, at barangay level — not a single extent map. The viewer refuses to show anything the satellite record does not support: observed dates only, ranges not point values, missing data never zero-filled.

## Operating Context

- Live hackathon demo on desktop, venue internet and GPU unknown; mobile must remain usable (bottom sheet) but is secondary.
- Static hosting, no backend. MapLibre GL JS with tilted perspective (isometric-inspired, not true isometric).
- Data sources requiring visible attribution: OpenStreetMap / Protomaps, Copernicus GLO-30, NAMRIA and PSA via OCHA COD-AB (barangay geometry).

## Capabilities and Constraints

- In scope now: pan/zoom/rotate/pitch, reset view, select/clear barangay via map or searchable list, toggle boundaries/buildings, disabled timeline shell, explicit per-source loading and failure states, persistent attribution, "Not an official hazard map" notice.
- Out of scope now: any storm, flood, water, rainfall, or photo content.
- Terminology: barangay, PSGC, observed vs modeled vs unknown, "flooded for between X and Y days" (later phase).
- Undecided: which storm, which future metric, boundary vintage for historical joins.

## Brand Commitments

- Name: **MATA: Tanaw**, expansion *Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters*. Repo name `masaSARap` is internal.
- UI language: English.
- Voice: plain-language, honest about limits; prefer "observed on these dates" over implying continuous monitoring.

## Evidence on Hand

- Research brief PDF and architecture plan in repo root.
- 14 candidate barangay polygons (faeldon/philippines-json-maps), PSGC municipality code `0403411000`.
- No storm observations, flood maps, photos, statistics, or user testimonials exist. None may be fabricated or implied.

## Product Principles

1. Never show what wasn't observed. Empty means unknown, not zero.
2. The place comes first: Los Baños must be recognizable before anything else is explained.
3. Honesty is a feature to demonstrate, not a footnote.
4. Barangay is the unit people act on.

## Accessibility & Inclusion

Keyboard-accessible barangay list as alternative to map hit-testing; visible focus; screen-reader names; reduced motion for camera transitions; no reliance on color alone; color-blind-safe palette for future flood layers.
