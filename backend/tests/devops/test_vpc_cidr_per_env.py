"""Regression: beta and prod must use distinct VPC CIDRs."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TF_ENVS = _REPO_ROOT / "devops" / "terraform" / "environments"

_VPC_CIDR = re.compile(r'^\s*vpc_cidr\s*=\s*"(?P<value>[^"]+)"', re.MULTILINE)
_PUBLIC = re.compile(
    r"^\s*public_subnet_cidrs\s*=\s*\[(?P<body>[^\]]+)\]",
    re.MULTILINE,
)
_PRIVATE = re.compile(
    r"^\s*private_subnet_cidrs\s*=\s*\[(?P<body>[^\]]+)\]",
    re.MULTILINE,
)


def _cidr_list(body: str) -> list[str]:
    return re.findall(r'"([^"]+)"', body)


def _env_network(env: str) -> tuple[str, list[str], list[str]]:
    text = (_TF_ENVS / env / "main.tf").read_text(encoding="utf-8")
    vpc = _VPC_CIDR.search(text)
    public = _PUBLIC.search(text)
    private = _PRIVATE.search(text)
    assert vpc is not None, f"{env} must set vpc_cidr explicitly"
    assert public is not None, f"{env} must set public_subnet_cidrs"
    assert private is not None, f"{env} must set private_subnet_cidrs"
    return vpc.group("value"), _cidr_list(public.group("body")), _cidr_list(private.group("body"))


def test_beta_and_prod_use_distinct_vpc_cidrs() -> None:
    """Env wrappers must not both inherit the stack 10.20.0.0/16 default."""
    beta_vpc, beta_pub, beta_priv = _env_network("beta")
    prod_vpc, prod_pub, prod_priv = _env_network("prod")

    assert beta_vpc == "10.20.0.0/16"
    assert prod_vpc == "10.30.0.0/16"
    assert beta_vpc != prod_vpc

    assert beta_pub == ["10.20.0.0/24", "10.20.1.0/24"]
    assert beta_priv == ["10.20.10.0/24", "10.20.11.0/24"]
    assert prod_pub == ["10.30.0.0/24", "10.30.1.0/24"]
    assert prod_priv == ["10.30.10.0/24", "10.30.11.0/24"]

    assert set(beta_pub + beta_priv).isdisjoint(set(prod_pub + prod_priv))
