from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

try:
    from adapters.registry import adapter_for_institution
except ImportError:
    from pipeline.adapters.registry import adapter_for_institution


BASE_KEYWORDS = [
    "admission",
    "admissions",
    "entrance",
    "requirement",
    "requirements",
    "how-to-apply",
    "how to apply",
    "apply",
    "english",
    "math",
    "academic requirements",
]

GLOBAL_DEMOTE_TERMS = [
    "tuition",
    "fees",
    "scholarship",
    "events",
    "news",
    "calendar",
    "residence",
    "housing",
    "donate",
    "alumni",
    "privacy",
    "contact",
]


@dataclass(frozen=True)
class LinkCandidate:
    url: str
    text: str = ""


@dataclass(frozen=True)
class LinkProfile:
    boosts: tuple[str, ...] = tuple()
    demotes: tuple[str, ...] = tuple()
    max_links: int = 8


LINK_PROFILES: dict[str, LinkProfile] = {
    "generic": LinkProfile(),
    "nait": LinkProfile(
        boosts=(
            "nait.ca/admissions",
            "admission-requirements",
            "program-admission",
            "academic-requirements",
            "how-to-apply",
            "english-language",
        ),
        demotes=("campus-life", "continuing-education"),
    ),
    "macewan": LinkProfile(
        boosts=(
            "macewan.ca/apply-enrol/admissions",
            "admission-requirements",
            "course-requirements",
            "admission average",
            "how-to-apply",
        ),
        demotes=("open-house", "services/fees"),
    ),
    "norquest": LinkProfile(
        boosts=(
            "norquest.ca/programs",
            "admission-requirements",
            "program-requirements",
            "how-to-apply",
            "academic-upgrading",
        ),
        demotes=("student-services", "continuing-education"),
    ),
    "ualberta": LinkProfile(
        boosts=(
            "ualberta.ca/en/admissions/undergraduate/admission",
            "admission-requirements",
            "competitive-requirements",
            "subject-requirements",
            "high-school",
            "how-to-apply",
        ),
        demotes=("campus-life", "events", "residence", "student-services"),
        max_links=10,
    ),
}


def root_domain(host: str) -> str:
    parts = [p for p in str(host or "").strip().lower().split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return ".".join(parts)


def is_same_site(base_host: str, candidate_host: str) -> bool:
    base = str(base_host or "").strip().lower()
    candidate = str(candidate_host or "").strip().lower()
    if not base or not candidate:
        return False
    if candidate == base:
        return True
    if candidate.endswith("." + base) or base.endswith("." + candidate):
        return True
    return root_domain(candidate) == root_domain(base)


def link_profile_for_institution(institution: str) -> LinkProfile:
    adapter = adapter_for_institution(institution)
    return LINK_PROFILES.get(adapter.name, LINK_PROFILES["generic"])


def score_link(candidate: LinkCandidate, profile: LinkProfile) -> int:
    haystack = f"{candidate.url} {candidate.text}".lower()
    score = 0

    for term in BASE_KEYWORDS:
        if term in haystack:
            score += 2

    for term in profile.boosts:
        if term in haystack:
            score += 4

    for term in GLOBAL_DEMOTE_TERMS:
        if term in haystack:
            score -= 3

    for term in profile.demotes:
        if term in haystack:
            score -= 4

    if "admission requirements" in haystack or "admission requirement" in haystack:
        score += 3
    if "how to apply" in haystack or "how-to-apply" in haystack:
        score += 2
    if "competitive" in haystack and "admission" in haystack:
        score += 2

    return score


def pick_enrichment_links(
    base_url: str,
    links: Iterable[LinkCandidate],
    institution: str = "",
    limit: int | None = None,
) -> list[str]:
    base_host = urlparse(base_url).netloc.lower()
    profile = link_profile_for_institution(institution)
    target_limit = int(limit) if isinstance(limit, int) and limit > 0 else profile.max_links

    scored: list[tuple[int, int, str]] = []
    for candidate in links:
        url = candidate.url
        host = urlparse(url).netloc.lower()
        if host and not is_same_site(base_host, host):
            continue
        score = score_link(candidate, profile)
        if score <= 0:
            continue
        scored.append((score, len(url), url))

    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    return [url for _, _, url in scored[:target_limit]]
