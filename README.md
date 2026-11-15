# masaSARap

React and Vite starter with Tailwind CSS, GSAP, and React Router.

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. `npm run build` creates the production build; `npm run preview` serves it locally.

The map opens on Bay; zooming out is limited to the Laguna overview. Select a municipality pin or use the flood observations picker to open its records. The picker lists only municipalities present in the published flood index; missing observations are unknown, not dry. The About and Sources controls explain the project and its data limits.
## Data, references and licenses

The main sources include Copernicus Sentinel-1, NASA OPERA DSWx-S1, NASA–ISRO NISAR, ASF HyP3, Copernicus DEM GLO-30, ESA WorldCover, EOX Sentinel-2 cloudless, OpenStreetMap, OCHA COD-AB and DAHITI. See [project references](public/references.txt) for sources, tools, research and demo-video credits, and [data provenance](public/data/PROVENANCE.md) for versions, transformations and limitations.

EOX Sentinel-2 cloudless imagery is licensed CC BY-NC-SA 4.0, restricting use to non-commercial purposes. The team must verify undocumented asset permissions and add any other resources used before submitting.

Code was developed with AI assistance.

## Team

Lukas Bebis, Angelica Saavedra, Jed Cabacang, Dave Caidic, Jericon Esguerra and Anthony Espina.
