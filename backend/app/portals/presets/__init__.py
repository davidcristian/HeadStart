"""Curated employer presets — one module per portal (`presets/<portal_id>.py`)."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset
from app.portals.presets.adyen import PORTAL as adyen
from app.portals.presets.airbyte import PORTAL as airbyte
from app.portals.presets.airtable import PORTAL as airtable
from app.portals.presets.alchemy import PORTAL as alchemy
from app.portals.presets.amplitude import PORTAL as amplitude
from app.portals.presets.anyscale import PORTAL as anyscale
from app.portals.presets.appian import PORTAL as appian
from app.portals.presets.asml import PORTAL as asml
from app.portals.presets.atlassian import PORTAL as atlassian
from app.portals.presets.baseten import PORTAL as baseten
from app.portals.presets.benchling import PORTAL as benchling
from app.portals.presets.bosch import PORTAL as bosch
from app.portals.presets.box import PORTAL as box
from app.portals.presets.braze import PORTAL as braze
from app.portals.presets.calendly import PORTAL as calendly
from app.portals.presets.canva import PORTAL as canva
from app.portals.presets.carta import PORTAL as carta
from app.portals.presets.celonis import PORTAL as celonis
from app.portals.presets.characterai import PORTAL as characterai
from app.portals.presets.checkout import PORTAL as checkout
from app.portals.presets.checkr import PORTAL as checkr
from app.portals.presets.chime import PORTAL as chime
from app.portals.presets.clickhouse import PORTAL as clickhouse
from app.portals.presets.clickup import PORTAL as clickup
from app.portals.presets.cockroachlabs import PORTAL as cockroachlabs
from app.portals.presets.confluent import PORTAL as confluent
from app.portals.presets.contentful import PORTAL as contentful
from app.portals.presets.cresta import PORTAL as cresta
from app.portals.presets.crowdstrike import PORTAL as crowdstrike
from app.portals.presets.cvshealth import PORTAL as cvshealth
from app.portals.presets.decagon import PORTAL as decagon
from app.portals.presets.deliveroo import PORTAL as deliveroo
from app.portals.presets.docker import PORTAL as docker
from app.portals.presets.docusign import PORTAL as docusign
from app.portals.presets.endava import PORTAL as endava
from app.portals.presets.ericsson import PORTAL as ericsson
from app.portals.presets.faire import PORTAL as faire
from app.portals.presets.fastly import PORTAL as fastly
from app.portals.presets.fivetran import PORTAL as fivetran
from app.portals.presets.freshworks import PORTAL as freshworks
from app.portals.presets.gehealthcare import PORTAL as gehealthcare
from app.portals.presets.gemini import PORTAL as gemini
from app.portals.presets.gong import PORTAL as gong
from app.portals.presets.grab import PORTAL as grab
from app.portals.presets.grafana import PORTAL as grafana
from app.portals.presets.grammarly import PORTAL as grammarly
from app.portals.presets.gusto import PORTAL as gusto
from app.portals.presets.hashicorp import PORTAL as hashicorp
from app.portals.presets.hellofresh import PORTAL as hellofresh
from app.portals.presets.hightouch import PORTAL as hightouch
from app.portals.presets.hubspot import PORTAL as hubspot
from app.portals.presets.huggingface import PORTAL as huggingface
from app.portals.presets.inflection import PORTAL as inflection
from app.portals.presets.infosys import PORTAL as infosys
from app.portals.presets.intercom import PORTAL as intercom
from app.portals.presets.jetbrains import PORTAL as jetbrains
from app.portals.presets.jfrog import PORTAL as jfrog
from app.portals.presets.klaviyo import PORTAL as klaviyo
from app.portals.presets.langchain import PORTAL as langchain
from app.portals.presets.launchdarkly import PORTAL as launchdarkly
from app.portals.presets.marqeta import PORTAL as marqeta
from app.portals.presets.mcdonalds import PORTAL as mcdonalds
from app.portals.presets.mercury import PORTAL as mercury
from app.portals.presets.microstrategy import PORTAL as microstrategy
from app.portals.presets.midjourney import PORTAL as midjourney
from app.portals.presets.miro import PORTAL as miro
from app.portals.presets.mixpanel import PORTAL as mixpanel
from app.portals.presets.modal import PORTAL as modal
from app.portals.presets.n26 import PORTAL as n26
from app.portals.presets.navan import PORTAL as navan
from app.portals.presets.neo4j import PORTAL as neo4j
from app.portals.presets.neon import PORTAL as neon
from app.portals.presets.newrelic import PORTAL as newrelic
from app.portals.presets.nubank import PORTAL as nubank
from app.portals.presets.nuro import PORTAL as nuro
from app.portals.presets.onepassword import PORTAL as onepassword
from app.portals.presets.pagerduty import PORTAL as pagerduty
from app.portals.presets.paloaltonetworks import PORTAL as paloaltonetworks
from app.portals.presets.patreon import PORTAL as patreon
from app.portals.presets.pendo import PORTAL as pendo
from app.portals.presets.pinecone import PORTAL as pinecone
from app.portals.presets.planetscale import PORTAL as planetscale
from app.portals.presets.pleo import PORTAL as pleo
from app.portals.presets.posthog import PORTAL as posthog
from app.portals.presets.postman import PORTAL as postman
from app.portals.presets.proton import PORTAL as proton
from app.portals.presets.purestorage import PORTAL as purestorage
from app.portals.presets.redhat import PORTAL as redhat
from app.portals.presets.riotgames import PORTAL as riotgames
from app.portals.presets.ripple import PORTAL as ripple
from app.portals.presets.rippling import PORTAL as rippling
from app.portals.presets.rivian import PORTAL as rivian
from app.portals.presets.roblox import PORTAL as roblox
from app.portals.presets.roku import PORTAL as roku
from app.portals.presets.rtx import PORTAL as rtx
from app.portals.presets.rubrik import PORTAL as rubrik
from app.portals.presets.runway import PORTAL as runway
from app.portals.presets.samsara import PORTAL as samsara
from app.portals.presets.samsung import PORTAL as samsung
from app.portals.presets.sentinelone import PORTAL as sentinelone
from app.portals.presets.sentry import PORTAL as sentry
from app.portals.presets.servicenow import PORTAL as servicenow
from app.portals.presets.sierra import PORTAL as sierra
from app.portals.presets.sigma import PORTAL as sigma
from app.portals.presets.skroutz import PORTAL as skroutz
from app.portals.presets.smartsheet import PORTAL as smartsheet
from app.portals.presets.snap import PORTAL as snap
from app.portals.presets.snyk import PORTAL as snyk
from app.portals.presets.splunk import PORTAL as splunk
from app.portals.presets.squarespace import PORTAL as squarespace
from app.portals.presets.substack import PORTAL as substack
from app.portals.presets.temporal import PORTAL as temporal
from app.portals.presets.together import PORTAL as together
from app.portals.presets.twitch import PORTAL as twitch
from app.portals.presets.typeform import PORTAL as typeform
from app.portals.presets.unity3d import PORTAL as unity3d
from app.portals.presets.webflow import PORTAL as webflow
from app.portals.presets.westerndigital import PORTAL as westerndigital
from app.portals.presets.wise import PORTAL as wise
from app.portals.presets.wiz import PORTAL as wiz
from app.portals.presets.wlgore import PORTAL as wlgore
from app.portals.presets.wrike import PORTAL as wrike
from app.portals.presets.xai import PORTAL as xai
from app.portals.presets.zillow import PORTAL as zillow
from app.portals.presets.zoom import PORTAL as zoom
from app.portals.presets.zoominfo import PORTAL as zoominfo

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
    skroutz,
    typeform,
    wrike,
    intercom,
    postman,
    pleo,
    deliveroo,
    clickup,
    wise,
    sentry,
    jetbrains,
    contentful,
    onepassword,
    langchain,
    snap,
    together,
    modal,
    anyscale,
    runway,
    characterai,
    midjourney,
    pinecone,
    grafana,
    temporal,
    posthog,
    neon,
    planetscale,
    faire,
    gong,
    checkout,
    wlgore,
    newrelic,
    twitch,
    nubank,
    celonis,
    jfrog,
    mixpanel,
    airbyte,
    hightouch,
    gemini,
    ripple,
    alchemy,
    inflection,
    patreon,
    substack,
    grab,
    hellofresh,
    navan,
    appian,
    sierra,
    freshworks,
    decagon,
    cresta,
    smartsheet,
    zoominfo,
    baseten,
    proton,
    sigma,
    docker,
    neo4j,
    pendo,
)
