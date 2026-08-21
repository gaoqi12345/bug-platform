"""
Bug 状态机单测 — test_transitions.py
不依赖数据库，使用 FakeBug / FakeUser 对象直接测试规则表。
运行：cd backend && pytest tests/test_transitions.py -v
"""
import pytest
from app.core.transitions import validate_transition, _FALLBACK_RULES as TRANSITION_RULES
from app.models.enums import BugStatus


# ── 测试桩 ──────────────────────────────────────────────────────────────────

class FakeBug:
    def __init__(self, status: BugStatus, assignee_id: int | None = None, reporter_id: int = 99):
        self.status      = status
        self.assignee_id = assignee_id
        self.reporter_id = reporter_id


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


# ── NEW 状态 ─────────────────────────────────────────────────────────────────

class TestFromNew:
    def test_pm_can_assign(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "pm", {"assignee_id": 2})
        assert ok is True, err

    def test_assign_requires_assignee_id(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "pm", {})
        assert ok is False
        assert "assignee_id" in err

    def test_developer_cannot_assign(self):
        # developer 只能指派自己创建的，reporter_id=99，user.id=1，不匹配
        bug = FakeBug(BugStatus.NEW, reporter_id=99)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "developer", {"assignee_id": 2})
        assert ok is False

    def test_tester_cannot_assign(self):
        # tester 只能指派自己创建的，reporter_id=99，user.id=1，不匹配
        bug = FakeBug(BugStatus.NEW, reporter_id=99)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "tester", {"assignee_id": 2})
        assert ok is False

    def test_developer_can_assign_own_bug(self):
        # developer 可以指派自己创建的 bug
        bug = FakeBug(BugStatus.NEW, reporter_id=1)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "developer", {"assignee_id": 2})
        assert ok is True, err

    def test_tester_can_assign_own_bug(self):
        # tester 可以指派自己创建的 bug
        bug = FakeBug(BugStatus.NEW, reporter_id=1)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "tester", {"assignee_id": 2})
        assert ok is True, err

    def test_viewer_cannot_assign(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "viewer", {"assignee_id": 2})
        assert ok is False

    def test_pm_can_reject_new(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.REJECTED, FakeUser(1), "pm", {"reject_reason": "非缺陷"})
        assert ok is True, err

    def test_developer_can_reject_new(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.REJECTED, FakeUser(1), "developer", {"reject_reason": "已知行为"})
        assert ok is True, err

    def test_reject_requires_reason(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.REJECTED, FakeUser(1), "pm", {})
        assert ok is False
        assert "reject_reason" in err

    def test_cannot_jump_to_closed(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.CLOSED, FakeUser(1), "pm", {})
        assert ok is False

    def test_cannot_jump_to_resolved(self):
        bug = FakeBug(BugStatus.NEW)
        ok, err = validate_transition(bug, BugStatus.RESOLVED, FakeUser(1), "developer", {})
        assert ok is False


# ── ASSIGNED 状态 ─────────────────────────────────────────────────────────────

class TestFromAssigned:
    def test_assignee_can_start(self):
        bug = FakeBug(BugStatus.ASSIGNED, assignee_id=5)
        ok, err = validate_transition(bug, BugStatus.IN_PROGRESS, FakeUser(5), "developer", {})
        assert ok is True, err

    def test_non_assignee_cannot_start(self):
        bug = FakeBug(BugStatus.ASSIGNED, assignee_id=5)
        ok, err = validate_transition(bug, BugStatus.IN_PROGRESS, FakeUser(9), "developer", {})
        assert ok is False
        assert "指派人" in err or "条件" in err

    def test_pm_can_start_for_assignee(self):
        """pm 不受 assignee 条件限制，可以直接开始处理"""
        bug = FakeBug(BugStatus.ASSIGNED, assignee_id=5)
        ok, err = validate_transition(bug, BugStatus.IN_PROGRESS, FakeUser(1), "pm", {})
        assert ok is True, err

    def test_pm_can_reassign(self):
        bug = FakeBug(BugStatus.ASSIGNED, assignee_id=5)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "pm", {"assignee_id": 7})
        assert ok is True, err

    def test_developer_can_reject_assigned(self):
        bug = FakeBug(BugStatus.ASSIGNED, assignee_id=5)
        ok, err = validate_transition(bug, BugStatus.REJECTED, FakeUser(5), "developer", {"reject_reason": "重复"})
        assert ok is True, err


# ── IN_PROGRESS 状态 ──────────────────────────────────────────────────────────

class TestFromInProgress:
    def test_assignee_can_resolve(self):
        bug = FakeBug(BugStatus.IN_PROGRESS, assignee_id=3)
        ok, err = validate_transition(bug, BugStatus.RESOLVED, FakeUser(3), "developer",
                                      {"fix_description": "修复了空指针"})
        assert ok is True, err

    def test_resolve_requires_fix_description(self):
        bug = FakeBug(BugStatus.IN_PROGRESS, assignee_id=3)
        ok, err = validate_transition(bug, BugStatus.RESOLVED, FakeUser(3), "developer", {})
        assert ok is False
        assert "fix_description" in err

    def test_non_assignee_cannot_resolve(self):
        bug = FakeBug(BugStatus.IN_PROGRESS, assignee_id=3)
        ok, err = validate_transition(bug, BugStatus.RESOLVED, FakeUser(9), "developer",
                                      {"fix_description": "done"})
        assert ok is False

    def test_pm_can_reassign_from_in_progress(self):
        bug = FakeBug(BugStatus.IN_PROGRESS, assignee_id=3)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "pm", {"assignee_id": 4})
        assert ok is True, err


# ── RESOLVED 状态 ─────────────────────────────────────────────────────────────

class TestFromResolved:
    def test_tester_can_close(self):
        bug = FakeBug(BugStatus.RESOLVED)
        ok, err = validate_transition(bug, BugStatus.CLOSED, FakeUser(1), "tester", {})
        assert ok is True, err

    def test_pm_can_close(self):
        bug = FakeBug(BugStatus.RESOLVED)
        ok, err = validate_transition(bug, BugStatus.CLOSED, FakeUser(1), "pm", {})
        assert ok is True, err

    def test_developer_cannot_close(self):
        bug = FakeBug(BugStatus.RESOLVED)
        ok, err = validate_transition(bug, BugStatus.CLOSED, FakeUser(1), "developer", {})
        assert ok is False

    def test_tester_can_reopen(self):
        bug = FakeBug(BugStatus.RESOLVED)
        ok, err = validate_transition(bug, BugStatus.REOPENED, FakeUser(1), "tester",
                                      {"reopen_reason": "仍然复现"})
        assert ok is True, err

    def test_reopen_requires_reason(self):
        bug = FakeBug(BugStatus.RESOLVED)
        ok, err = validate_transition(bug, BugStatus.REOPENED, FakeUser(1), "tester", {})
        assert ok is False
        assert "reopen_reason" in err


# ── REJECTED 状态 ─────────────────────────────────────────────────────────────

class TestFromRejected:
    def test_tester_can_reopen_rejected(self):
        bug = FakeBug(BugStatus.REJECTED)
        ok, err = validate_transition(bug, BugStatus.REOPENED, FakeUser(1), "tester",
                                      {"reopen_reason": "不认可拒绝原因"})
        assert ok is True, err

    def test_developer_cannot_reopen_rejected(self):
        bug = FakeBug(BugStatus.REJECTED)
        ok, err = validate_transition(bug, BugStatus.REOPENED, FakeUser(1), "developer",
                                      {"reopen_reason": "重新评估"})
        assert ok is False


# ── CLOSED 状态 ───────────────────────────────────────────────────────────────

class TestFromClosed:
    def test_tester_can_reopen_closed(self):
        bug = FakeBug(BugStatus.CLOSED)
        ok, err = validate_transition(bug, BugStatus.REOPENED, FakeUser(1), "tester",
                                      {"reopen_reason": "回归测试发现复现"})
        assert ok is True, err

    def test_cannot_directly_close_again(self):
        bug = FakeBug(BugStatus.CLOSED)
        ok, err = validate_transition(bug, BugStatus.CLOSED, FakeUser(1), "pm", {})
        assert ok is False


# ── REOPENED 状态 ─────────────────────────────────────────────────────────────

class TestFromReopened:
    def test_pm_can_assign_reopened(self):
        bug = FakeBug(BugStatus.REOPENED)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "pm", {"assignee_id": 2})
        assert ok is True, err

    def test_tester_cannot_assign_reopened(self):
        # tester 只能指派自己创建的，reporter_id=99，user.id=1，不匹配
        bug = FakeBug(BugStatus.REOPENED, reporter_id=99)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "tester", {"assignee_id": 2})
        assert ok is False

    def test_tester_can_assign_own_reopened(self):
        # tester 可以指派自己创建的 reopened bug
        bug = FakeBug(BugStatus.REOPENED, reporter_id=1)
        ok, err = validate_transition(bug, BugStatus.ASSIGNED, FakeUser(1), "tester", {"assignee_id": 2})
        assert ok is True, err


# ── 规则完整性检查 ────────────────────────────────────────────────────────────

class TestRuleIntegrity:
    def test_all_rules_have_roles(self):
        """每条规则都必须有 allowed_roles 字段"""
        for key, rule in TRANSITION_RULES.items():
            assert "allowed_roles" in rule, f"规则 {key} 缺少 allowed_roles 字段"
            assert len(rule["allowed_roles"]) > 0, f"规则 {key} 的 allowed_roles 不能为空"

    def test_all_roles_are_strings(self):
        """allowed_roles 中的值必须全部是纯字符串（不能混入枚举对象）"""
        for key, rule in TRANSITION_RULES.items():
            for role in rule["allowed_roles"]:
                assert isinstance(role, str), \
                    f"规则 {key} 中的角色 {role!r} 不是字符串（枚举/字符串混用 bug）"

    def test_all_required_fields_are_lists(self):
        """required_fields 必须是列表"""
        for key, rule in TRANSITION_RULES.items():
            if "required_fields" in rule:
                assert isinstance(rule["required_fields"], list), \
                    f"规则 {key} 的 required_fields 不是列表"

    def test_valid_status_values_in_keys(self):
        """规则 key 中的状态值必须是合法的 BugStatus"""
        valid = set(s.value for s in BugStatus)
        for (from_s, to_s) in TRANSITION_RULES.keys():
            assert from_s in valid, f"非法的 from_status: {from_s}"
            assert to_s   in valid, f"非法的 to_status: {to_s}"
