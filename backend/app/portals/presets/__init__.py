"""Curated employer presets — one module per portal (`presets/<portal_id>.py`)."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset
from app.portals.presets.checkr import PORTAL as checkr
from app.portals.presets.chime import PORTAL as chime
from app.portals.presets.fastly import PORTAL as fastly
from app.portals.presets.gusto import PORTAL as gusto
from app.portals.presets.hubspot import PORTAL as hubspot
from app.portals.presets.klaviyo import PORTAL as klaviyo
from app.portals.presets.mercury import PORTAL as mercury
from app.portals.presets.pagerduty import PORTAL as pagerduty
from app.portals.presets.purestorage import PORTAL as purestorage
from app.portals.presets.riotgames import PORTAL as riotgames
from app.portals.presets.roblox import PORTAL as roblox
from app.portals.presets.samsara import PORTAL as samsara
from app.portals.presets.squarespace import PORTAL as squarespace
from app.portals.presets.unity3d import PORTAL as unity3d
from app.portals.presets.zoom import PORTAL as zoom

PORTALS: tuple[PortalPreset, ...] = (
    hubspot,
    zoom,
    gusto,
    purestorage,
    unity3d,
    samsara,
    roblox,
    klaviyo,
    riotgames,
    chime,
    checkr,
    mercury,
    fastly,
    pagerduty,
    squarespace,
)
