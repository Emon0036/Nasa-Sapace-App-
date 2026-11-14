# LOLA south-polar terrain tiles

These GeoTIFFs are NASA GSFC Planetary Geology, Geophysics and Geochemistry
Laboratory (PGDA) high-resolution LRO-LOLA elevation products. The project uses
the adjusted surface-elevation grids for Site01 (Connecting Ridge), Site04
(Shackleton rim), Site07 (Peak near Shackleton), and Site20 (Leibnitz Beta
plateau). Each is a 5 m/pixel regional tile in south-polar stereographic X/Y
coordinates, Moon_ME frame tied to DE421.

The products are derived from LOLA laser altimetry. NASA notes that roughly 90%
of the 5 m pixels are interpolated because the laser tracks do not independently
sample every pixel. The application labels these as interpolated LOLA DEM
products and displays the complete ray-trace radius used for each profile.

## Source and citation

- Product description and data links: <https://pgda.gsfc.nasa.gov/products/78>
- PDS LOLA Gridded Data Record dataset DOI: <https://doi.org/10.17189/1520642>
- Citation: NASA GSFC Planetary Geology, Geophysics and Geochemistry Laboratory.
  *High-Resolution LOLA Topography for Lunar South Pole Sites*, PGDA product 78.

## Rebuild horizon profiles

For local development, install the project requirements, fetch the source tiles
with their recorded checksum validation, then run from the repository root:

```powershell
python data_pipeline/fetch_deployment_assets.py
python data_pipeline/build_lola_horizons.py
```

The Render build runs the same asset fetch automatically. The large GeoTIFFs
are not stored in Git; deployment obtains them from the NASA URLs listed in
`provenance.json` and verifies each byte count and SHA-256 digest before use.

The script creates `data/terrain/lola/provenance.json` and writes profiles to
`data/horizons/` only when a source tile contains valid terrain over a complete
radius in all 360 azimuth bins. It tries radii from 5 km down to 250 m. Profiles
shorter than 5 km represent only local terrain; terrain beyond that radius is
not modeled. During custom-site analysis, the API can also generate and cache a
matching profile from the same tiles. Each profile records its actual radius
and source. If no complete circle is covered, visibility uses the geometric
horizon; synthetic horizon graphics remain display-only.

The coordinates in `src/sites.py` are nominal prototype coordinates. A DEM is
used only where the requested coordinate falls inside its georeferenced tile.
