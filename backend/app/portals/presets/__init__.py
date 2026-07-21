"""Curated employer presets — one module per portal (`presets/<portal_id>.py`)."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset
from app.portals.presets.adyen import PORTAL as adyen
from app.portals.presets.airtable import PORTAL as airtable
from app.portals.presets.amplitude import PORTAL as amplitude
from app.portals.presets.asml import PORTAL as asml
from app.portals.presets.atlassian import PORTAL as atlassian
from app.portals.presets.benchling import PORTAL as benchling
from app.portals.presets.bosch import PORTAL as bosch
from app.portals.presets.box import PORTAL as box
from app.portals.presets.braze import PORTAL as braze
from app.portals.presets.calendly import PORTAL as calendly
from app.portals.presets.canva import PORTAL as canva
from app.portals.presets.carta import PORTAL as carta
from app.portals.presets.checkr import PORTAL as checkr
from app.portals.presets.chime import PORTAL as chime
from app.portals.presets.clickhouse import PORTAL as clickhouse
from app.portals.presets.cockroachlabs import PORTAL as cockroachlabs
from app.portals.presets.confluent import PORTAL as confluent
from app.portals.presets.crowdstrike import PORTAL as crowdstrike
from app.portals.presets.cvshealth import PORTAL as cvshealth
from app.portals.presets.docusign import PORTAL as docusign
from app.portals.presets.endava import PORTAL as endava
from app.portals.presets.ericsson import PORTAL as ericsson
from app.portals.presets.fastly import PORTAL as fastly
from app.portals.presets.fivetran import PORTAL as fivetran
from app.portals.presets.gehealthcare import PORTAL as gehealthcare
from app.portals.presets.grammarly import PORTAL as grammarly
from app.portals.presets.gusto import PORTAL as gusto
from app.portals.presets.hashicorp import PORTAL as hashicorp
from app.portals.presets.hubspot import PORTAL as hubspot
from app.portals.presets.huggingface import PORTAL as huggingface
from app.portals.presets.infosys import PORTAL as infosys
from app.portals.presets.klaviyo import PORTAL as klaviyo
from app.portals.presets.launchdarkly import PORTAL as launchdarkly
from app.portals.presets.marqeta import PORTAL as marqeta
from app.portals.presets.mcdonalds import PORTAL as mcdonalds
from app.portals.presets.mercury import PORTAL as mercury
from app.portals.presets.microstrategy import PORTAL as microstrategy
from app.portals.presets.miro import PORTAL as miro
from app.portals.presets.n26 import PORTAL as n26
from app.portals.presets.nuro import PORTAL as nuro
from app.portals.presets.pagerduty import PORTAL as pagerduty
from app.portals.presets.paloaltonetworks import PORTAL as paloaltonetworks
from app.portals.presets.purestorage import PORTAL as purestorage
from app.portals.presets.redhat import PORTAL as redhat
from app.portals.presets.riotgames import PORTAL as riotgames
from app.portals.presets.rippling import PORTAL as rippling
from app.portals.presets.rivian import PORTAL as rivian
from app.portals.presets.roblox import PORTAL as roblox
from app.portals.presets.roku import PORTAL as roku
from app.portals.presets.rtx import PORTAL as rtx
from app.portals.presets.rubrik import PORTAL as rubrik
from app.portals.presets.samsara import PORTAL as samsara
from app.portals.presets.samsung import PORTAL as samsung
from app.portals.presets.sentinelone import PORTAL as sentinelone
from app.portals.presets.servicenow import PORTAL as servicenow
from app.portals.presets.snyk import PORTAL as snyk
from app.portals.presets.splunk import PORTAL as splunk
from app.portals.presets.squarespace import PORTAL as squarespace
from app.portals.presets.unity3d import PORTAL as unity3d
from app.portals.presets.webflow import PORTAL as webflow
from app.portals.presets.westerndigital import PORTAL as westerndigital
from app.portals.presets.wiz import PORTAL as wiz
from app.portals.presets.xai import PORTAL as xai
from app.portals.presets.zillow import PORTAL as zillow
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
    rivian,
    rippling,
    chime,
    checkr,
    mercury,
    fastly,
    pagerduty,
    squarespace,
    atlassian,
    bosch,
    servicenow,
    westerndigital,
    samsung,
    asml,
    ericsson,
    infosys,
    docusign,
    microstrategy,
    endava,
    mcdonalds,
    canva,
    roku,
    braze,
    adyen,
    wiz,
    fivetran,
    rubrik,
    nuro,
    n26,
    carta,
    confluent,
    airtable,
    marqeta,
    crowdstrike,
    zillow,
    paloaltonetworks,
    sentinelone,
    splunk,
    grammarly,
    snyk,
    hashicorp,
    redhat,
    box,
    launchdarkly,
    amplitude,
    benchling,
    cockroachlabs,
    webflow,
    calendly,
    miro,
    xai,
    cvshealth,
    gehealthcare,
    rtx,
    clickhouse,
    huggingface,
)
