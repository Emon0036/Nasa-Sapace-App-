# Mission viewport textures

These bundled images are visual textures only. They do not feed the ephemeris, terrain horizon, telemetry, or mission scoring calculations.

| File | Source | Use |
| --- | --- | --- |
| `earth-blue-marble-2048.png` | NASA Goddard Scientific Visualization Studio, [Blue Marble: A Seamless Image Mosaic of the Earth](https://svs.gsfc.nasa.gov/2915/). The map is based largely on MODIS observations and is credited by NASA to Reto Stöckli and NASA Earth Observatory. | Earth color map for the animated Three.js globe. |
| `moon-lroc-color-2k.jpg` | NASA Goddard Scientific Visualization Studio, [CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/). The color map is derived from LRO camera imagery. NASA describes it as an aesthetic rendering map, not a scientific data product. | Moon color map for the animated Three.js globe. |

Lighting, the Earth atmosphere, and lunar crater relief are rendered in the viewport. The spacecraft path and mission phase timing are illustrative. Surface Sun/Earth telemetry and the horizon profile continue to come from the FastAPI mission plan.
