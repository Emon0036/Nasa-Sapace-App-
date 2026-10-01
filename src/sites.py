"""
Candidate lunar south polar landing sites.

Coordinates are approximate IAU_MOON selenographic. Elevations are rough
baselines from LOLA; the horizon profile carries the actual terrain detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Site:
    site_id: str
    name: str
    lat_deg: float
    lon_deg: float
    elev_m: float
    description: str
    region: str  # "south_polar", "north_polar", "reference"


# Source: NASA Artemis III candidate region announcements + LOLA elevations.
SITES: Dict[str, Site] = {
    "shackleton_henson": Site(
        site_id="shackleton_henson",
        name="Shackleton-Henson Connecting Ridge",
        lat_deg=-89.45,
        lon_deg=160.0,
        elev_m=1450.0,
        description=("Connecting ridge between Shackleton and Henson craters; "
                     "Artemis III candidate. Excellent Earth visibility and "
                     "moderate sunlit fractions in summer."),
        region="south_polar",
    ),
    "shackleton_rim_e": Site(
        site_id="shackleton_rim_e",
        name="Shackleton Rim (East)",
        lat_deg=-89.65,
        lon_deg=141.0,
        elev_m=2050.0,
        description=("Eastern rim of Shackleton crater, near permanently "
                     "illuminated regions. Steep local terrain."),
        region="south_polar",
    ),
    "shackleton_rim_w": Site(
        site_id="shackleton_rim_w",
        name="Shackleton Rim (West)",
        lat_deg=-89.55,
        lon_deg=225.0,
        elev_m=1850.0,
        description=("Western rim of Shackleton. Lower illumination than the "
                     "east rim but slightly easier terrain."),
        region="south_polar",
    ),
    "shackleton_rim_n": Site(
        site_id="shackleton_rim_n",
        name="Shackleton Rim (North)",
        lat_deg=-89.20,
        lon_deg=0.0,
        elev_m=1500.0,
        description=("Northern rim of Shackleton. Frequently cited Artemis III "
                     "candidate for slope/sunlight balance."),
        region="south_polar",
    ),
    "de_la_rue": Site(
        site_id="de_la_rue",
        name="de la Rue",
        lat_deg=-88.50,
        lon_deg=60.0,
        elev_m=600.0,
        description=("Rim of de la Rue crater; broader, flatter area south of "
                     "the pole with longer sunlight windows."),
        region="south_polar",
    ),
    "leibnitz_beta": Site(
        site_id="leibnitz_beta",
        name="Leibnitz Beta",
        lat_deg=-85.40,
        lon_deg=20.0,
        elev_m=500.0,
        description=("Beta peak near Leibnitz crater; reference site with good "
                     "Earth visibility and partial illumination."),
        region="south_polar",
    ),
    "cabeus": Site(
        site_id="cabeus",
        name="Cabeus (LCROSS)",
        lat_deg=-84.90,
        lon_deg=-35.5,
        elev_m=-1100.0,
        description=("LCROSS impact site. Permanently shadowed floor (cold "
                     "trap); included for reference."),
        region="south_polar",
    ),
    "peary": Site(
        site_id="peary",
        name="Peary (N. pole ref.)",
        lat_deg=88.50,
        lon_deg=30.0,
        elev_m=900.0,
        description=("Northern pole reference site for symmetry comparison."),
        region="north_polar",
    ),
    "flat_reference": Site(
        site_id="flat_reference",
        name="Flat Reference (no terrain)",
        lat_deg=-89.50,
        lon_deg=0.0,
        elev_m=0.0,
        description=("Synthetic flat site at high latitude; useful for "
                     "isolating the geometric (non-terrain) effects."),
        region="reference",
    ),
}


def get_site(site_id: str) -> Site:
    if site_id not in SITES:
        raise KeyError(f"Unknown site: {site_id}. Options: {list(SITES)}")
    return SITES[site_id]


def all_sites():
    return list(SITES.values())


def south_polar_sites():
    return [s for s in all_sites() if s.region == "south_polar"]
