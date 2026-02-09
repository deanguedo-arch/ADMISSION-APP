from __future__ import annotations

from .base import InstitutionAdapter
from .generic import GenericAdapter
from .macewan import MacEwanAdapter
from .nait import NaitAdapter
from .norquest import NorQuestAdapter
from .ualberta import UAlbertaAdapter


_ADAPTERS: list[InstitutionAdapter] = [
    NaitAdapter(),
    MacEwanAdapter(),
    NorQuestAdapter(),
    UAlbertaAdapter(),
]
_GENERIC = GenericAdapter()

_ADAPTER_MAP: dict[str, InstitutionAdapter] = {}
for adapter in _ADAPTERS:
    for institution in adapter.institutions:
        _ADAPTER_MAP[institution.strip().upper()] = adapter


def adapter_for_institution(institution: str) -> InstitutionAdapter:
    key = str(institution or "").strip().upper()
    return _ADAPTER_MAP.get(key, _GENERIC)
