import enum


class BugStatus(str, enum.Enum):
    NEW         = "new"
    ASSIGNED    = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED    = "resolved"
    CLOSED      = "closed"
    REJECTED    = "rejected"
    REOPENED    = "reopened"


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class Priority(str, enum.Enum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class TeamRole(str, enum.Enum):
    ADMIN  = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class ProjectRole(str, enum.Enum):
    PM        = "pm"
    DEVELOPER = "developer"
    TESTER    = "tester"
    VIEWER    = "viewer"


class VersionStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE   = "active"
    RELEASED = "released"
    ARCHIVED = "archived"


class CaseRunResult(str, enum.Enum):
    PASSED  = "passed"
    FAILED  = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
