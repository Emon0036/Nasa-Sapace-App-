# NAIF SPICE kernel provenance

These kernels were downloaded from the official NAIF generic-kernel archive for the local DE440 SPICE backend. The Moon frame kernel identifies the binary lunar orientation PCK it is paired with.

| File | NAIF source | Type / purpose | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| `de440s.bsp` | [NAIF planetary SPK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp) | DE440 short planetary ephemeris | 32,726,016 | `C1C7FEEAB882263FC493A9D5A5B2DDD71B54826CDF65D8D17A76126B260A49F2` |
| `naif0012.tls` | [NAIF leap-second kernel](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls) | Leap-second table for UTC to ET conversion | 5,257 | `678E32BDB5A744117A467CD9601CD6B373F0E9BC9BBDE1371D5EEE39600A039B` |
| `pck00011.tpc` | [NAIF planetary constants](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc) | Text PCK constants and body radii | 131,226 | `3DFF7B1DBECEAA01F25467767D3FA25816051C85D162D1EDF04ACB310EE28BB1` |
| `moon_pa_de440_200625.bpc` | [NAIF lunar binary PCK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc) | Time-dependent DE440 lunar orientation | 12,863,488 | `60CD55AA401EA2EA97360636F567554BFE4E37BB829F901B4460A455DFAF783F` |
| `moon_de440_250416.tf` | [NAIF lunar frame kernel](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf) | Defines `MOON_PA`, `MOON_ME`, `MOON_PA_DE440`, and `MOON_ME_DE440_ME421` frames | 19,478 | `A47C71E9C9F33796BDAFB2C9D69A7EE447B6016ECAD80F71CD6F3E479F9CF768` |

The `moon_pa_de440_200625` file is a **binary PCK (`.bpc`)**, not a text frame kernel (`.tf`). The corresponding frame definitions are in `moon_de440_250416.tf`. The runtime loads constants and frame definitions before the binary orientation PCK.

The calculations use the `MOON_ME` frame so the user-entered east-positive geodetic coordinates match the Horizons high-precision mean-Earth observer convention. The SPICE position vectors are in km, and time is converted from UTC to ephemeris time using the loaded leap-second kernel.

Kernel hashes are included so a replacement download can be checked before use. Sources and acquisition details are retained here; the JPL Horizons processed-data provenance is in `data/processed/horizons_ephemeris.provenance.json`.

The lunar frame kernel and large binary lunar orientation PCK are downloaded
and SHA-256 verified by `data_pipeline/fetch_deployment_assets.py` during
deployment; neither is stored in Git.
