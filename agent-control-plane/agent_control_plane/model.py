from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


@dataclass(frozen=True)
class Evaluation:
    decision: Decision
    rule_id: str
    reason: str
    risk_score: int
    blast_radius: str
    irreversible: bool
    approval_group: str | None = None
    matched_conditions: tuple[str, ...] = ()
