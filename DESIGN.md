# MATA: Tanaw — Design

Decided 2026-11-14. Evidence boards in `.impeccable/mocks/decision/`.

## Visual world (authority: `V3-model.png`)

Golden-hour relief: steep oblique pitch (~60–65°) looking south from Laguna de Bay to Mount Makiling, warm hillshade, crisp extruded buildings, lake in the foreground. The UI floats over the full-bleed map as separate rounded cards: one full-width navbar, barangay card on the right, timeline pill at the bottom, map controls and a bearing/pitch readout at the lower left.

Map palette (from the Alive Maps reference): land `#F2EFE0`, lake `#11B5AE`, mint park `#8ED9AF`, forest `#3E9B5A`, major road `#E8807F`.

Canopy and ground: Sentinel-2 cloudless 2024 (EOX) imagery on the terrain gives forest and paddy texture zoomed out and fades out by z15.5, before its 10 m pixels blur street-level detail. From z14, low-poly three.js trees (instanced, two levels of detail) stand on the terrain; mapped OSM trees and decorative fill share one look, and Sources discloses the fill. Buildings are plaster-white with a thin roof cap in muted roof colours, grounded by a blurred contact rim and an offset shadow. Over imagery, unselected barangay lines lose contrast on dark forest; the selection casing still holds.

Time of day: a sun/moon control sets the Manila clock (default 15:30) for lighting only. The real sun position over Bay drives sky, extrusion light, hillshade direction and a night wash. Building shadows follow the sun's direction and length, but only roughly: MapLibre can only shift a whole layer, so buildings are grouped into three height bands with one offset each. Trees keep fixed lighting.

## Colour: Cobalt on Chalk

| Token | Hex | Use |
|---|---|---|
| ink | `#0F1B33` | text, 16.4:1 on chalk |
| muted | `#56607A` | secondary text |
| cobalt | `#1F4FD8` | the only accent: active chips, selection line, label pill, focus |
| cobalt-tint | `#E7EDFC` | status chips, empty-state wells; cobalt-ink text `#1F3FA8` |
| chalk | `#FBFAF6` | cards, navbar |
| page | `#F7F5EF` | page and app ground |
| line | `#DDE1EA` | card borders, dividers |

Selection: 5 px cobalt line over an 11 px white casing, with a ~25 % cobalt fill. Measured contrast of the blue line against each ground: land 5.7:1, mint 4.0:1, forest 1.9:1 (the white casing brings that to 3.5:1). On the lake, blue is 2.6:1 and the casing 2.5:1, both below the 3:1 target; acceptable only at the shoreline edge. Status colours (states only, never decoration): ok `#15826B`, warn `#B7791F`, fail `#C2412D`.

## Typography: Geist family (`geist` npm 1.9.2, OFL)

- Display (wordmark, barangay names, section titles): **Geist 500**. No heavy weights.
- UI text: Geist 400, labels and chips 500.
- Identifiers and readings (PSGC, bearing/pitch, counts): **Geist Mono** 400–500.

## Voice: Field log

Terse, label first, then the fact. An instrument reporting status.

- Navbar: search `Barangay or PSGC` · status chip `Observations: 84 Sentinel-1 dates` or `Observations: none loaded` (never `0`: a zero reads as "no flooding") · `Sources`
- Empty sidebar: `No barangay selected` / `15 barangays · Bay, Laguna. Select on map or list.`
- Selected sidebar: rows `PSGC`, `Municipality`, `Geometry`; section `This pass` → `Flooded` / `No flood seen` / `Unknown` across all sources, `Seen by …`, open-water and low-confidence hectares, `Second opinions` (one verdict per source: `Flood signal` / `None seen` / `No acquisition`), then `Flooded runs` as `between X and Y days` (or `upper bound unknown`) with `seen by …`.
- Timeline: one stop per observed pass, labelled in Philippine time with satellite and `N d after previous`, so 6- and 12-day jumps never read as daily.
- Flood overlay: a lit water surface that follows the terrain, with smoothed shorelines. Confident flood is deep blue; low confidence is the same water, paler and fainter; grey veil for unknown (no data, steep, or radar-blind built-up and tree cover). Unknown is never drawn as dry; the barangay card says `No flood seen` and how much of the barangay the radar can see, never `No flood`.
- Evidence overlays (toggles under Buildings): built-up coherence loss in solid amber, NISAR HV darkening in solid cyan, drawn flat with the same smoothed edges. They stay apart from the water by colour and by lacking its reflections; the amber is the design status colour, so it is not the only cue (the toggle labels name them).
- States: `Terrain · loading` (`GLO-30 tiles`), `Terrain · unavailable` (`Flat fallback. Elevation not rendered.`), `Boundaries · failed` (`Selection disabled.`)
- Disclaimer: `Not an official hazard map`
- Sources panel: `Elevation · GLO-30` / `Buildings · OSM` / `Boundaries · COD-AB`, one line each on the limits.

Rule: any count about storm data says "none loaded", never 0.
