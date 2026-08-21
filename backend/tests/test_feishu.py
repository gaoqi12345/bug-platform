"""
飞书通知 + 卡片回调单测 — test_feishu.py
- _load_feishu_cfg 开关逻辑（DB 读取 / 兜底 / 缓存失效）
- _build_private_card 按钮按状态渲染
- handle_card_action 回调处理（open_id 映射 / 状态流转 / 响应卡片）
- apply_bug_transition service 层（SQLite 内存库，monkeypatch 权限与规则）

运行：cd backend && pytest tests/test_feishu.py -v
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.user import User          # noqa: F401
from app.models.version import Version    # noqa: F401 — 必须导入，触发 mapper 注册
from app.models.bug import Bug, BugHistory  # noqa: F401 — 触发 mapper 注册
from app.models.team import Team, TeamMember  # noqa: F401
from app.models.project import Project, ProjectMembership  # noqa: F401
from app.models.enums import BugStatus, Priority
from app.core.security import hash_password

from app.services import notify_service
from app.api.v1 import feishu_callback


# ── 测试数据库（SQLite 内存，无外部依赖）────────────────────────────────

@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 预置两个用户：一个绑定了飞书 open_id，一个未绑定
    bound   = User(email="bound@t.com",    display_name="绑定用户", password_hash=hash_password("x"),
                   feishu_open_id="ou_bound_user_001")
    unbound = User(email="unbound@t.com",  display_name="未绑定用户", password_hash=hash_password("x"))
    session.add_all([bound, unbound])
    session.flush()
    session.bound_id   = bound.id
    session.unbound_id = unbound.id
    session.bound_open_id = bound.feishu_open_id

    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ── _load_feishu_cfg：DB 读取与兜底 ────────────────────────────────────

class FakeRow:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class FakeDB:
    """模拟 SessionLocal().execute() 返回的 session"""
    def __init__(self, data: dict):
        self._data = data

    def execute(self, stmt, params=None):
        data = self._data

        class Result:
            def fetchall(self):
                return [FakeRow(k, v) for k, v in data.items()]

        return Result()

    def close(self):
        pass


def _patch_session(monkeypatch, data: dict):
    """让 notify_service 内部的 SessionLocal 返回 FakeDB"""
    import app.db.session as db_session_module
    monkeypatch.setattr(db_session_module, "SessionLocal", lambda: FakeDB(data))


class TestLoadFeishuCfg:
    def setup_method(self):
        notify_service.invalidate_cache()

    def test_defaults_when_db_empty(self, monkeypatch):
        """DB 无记录时：群开关默认开（兼容旧行为），私聊默认关"""
        _patch_session(monkeypatch, {})
        cfg = notify_service._load_feishu_cfg()
        assert cfg["group_notify_enabled"] is True
        assert cfg["private_notify_enabled"] is False
        assert cfg["app_id"] == ""

    def test_reads_from_db(self, monkeypatch):
        """DB 有记录时按记录解析"""
        _patch_session(monkeypatch, {
            "feishu_group_notify_enabled": "false",
            "feishu_private_notify_enabled": "true",
            "feishu_app_id": "cli_test_app",
            "feishu_app_secret": "sec",
            "feishu_verification_token": "tok",
        })
        cfg = notify_service._load_feishu_cfg()
        assert cfg["group_notify_enabled"] is False
        assert cfg["private_notify_enabled"] is True
        assert cfg["app_id"] == "cli_test_app"
        assert cfg["app_secret"] == "sec"

    def test_cache_and_invalidate(self, monkeypatch):
        """缓存生效：修改 DB 后未失效前读旧值，invalidate_cache 后读新值"""
        _patch_session(monkeypatch, {"feishu_private_notify_enabled": "false"})
        assert notify_service._load_feishu_cfg()["private_notify_enabled"] is False

        _patch_session(monkeypatch, {"feishu_private_notify_enabled": "true"})
        assert notify_service._load_feishu_cfg()["private_notify_enabled"] is False  # 仍走缓存

        notify_service.invalidate_cache()
        assert notify_service._load_feishu_cfg()["private_notify_enabled"] is True


# ── _build_private_card：按钮按状态渲染 ────────────────────────────────

class TestBuildPrivateCard:
    def _buttons(self, status: str):
        card = notify_service._build_private_card(
            bug_id=1, title="测试", priority="p1", description="描述",
            assignee_name="张三", reporter_name="李四", status=status,
        )
        return [e for e in card["card"]["body"]["elements"] if e.get("tag") == "button"]

    def _callback_buttons(self, status: str) -> list:
        """仅返回带 callback 交互的按钮"""
        btns = self._buttons(status)
        return [b for b in btns if any(
            bh.get("type") == "callback" for bh in b.get("behaviors", []))]

    def test_assigned_shows_start_button(self):
        callbacks = self._callback_buttons("assigned")
        values = [bh["value"] for b in callbacks for bh in b["behaviors"] if bh.get("type") == "callback"]
        assert {"bug_id": 1, "action": "start"} in values

    def test_in_progress_shows_resolve_button(self):
        callbacks = self._callback_buttons("in_progress")
        values = [bh["value"] for b in callbacks for bh in b["behaviors"] if bh.get("type") == "callback"]
        assert {"bug_id": 1, "action": "resolve"} in values

    def test_resolved_has_no_action_buttons(self):
        assert self._callback_buttons("resolved") == []

    def test_always_has_detail_link(self):
        btns = self._buttons("new")
        assert any(
            b["behaviors"][0]["type"] == "open_url" and "bugs/1" in b["behaviors"][0].get("default_url", "")
            for b in btns
        )


# ── _bug_status_str：兼容 Bug 对象与枚举值两种传参 ─────────────────────

class TestBugStatusStr:
    def test_bug_object_returns_status(self):
        """传 Bug 对象 → 取 bug.status 枚举值"""
        bug = type("FakeBug", (), {"status": BugStatus.IN_PROGRESS})()
        assert notify_service._bug_status_str(bug) == "in_progress"

    def test_priority_enum_returns_value(self):
        """传 Priority 枚举 → 直接取 value（回归：曾抛 AttributeError）"""
        assert notify_service._bug_status_str(Priority.P1) == "p1"

    def test_status_enum_returns_value(self):
        """传 BugStatus 枚举 → 直接取 value"""
        assert notify_service._bug_status_str(BugStatus.ASSIGNED) == "assigned"


# ── 回调校验 ────────────────────────────────────────────────────────────

class TestVerifyToken:
    def setup_method(self):
        notify_service.invalidate_cache()

    def test_mismatch_rejected(self, monkeypatch):
        _patch_session(monkeypatch, {"feishu_verification_token": "expect"})
        assert feishu_callback._verify_token("wrong") is False

    def test_match_accepted(self, monkeypatch):
        _patch_session(monkeypatch, {"feishu_verification_token": "expect"})
        assert feishu_callback._verify_token("expect") is True

    def test_no_token_configured_accepts(self, monkeypatch):
        _patch_session(monkeypatch, {})
        assert feishu_callback._verify_token("anything") is True


# ── handle_card_action：回调处理 ───────────────────────────────────────

class TestHandleCardAction:
    def test_missing_operator(self, db):
        resp = feishu_callback.handle_card_action({"operator": {}, "action": {"value": {"bug_id": 1, "action": "start"}}}, db)
        assert resp["data"]["toast"]["type"] == "error"
        assert "绑定" in resp["data"]["toast"]["content"]

    def test_invalid_action(self, db):
        resp = feishu_callback.handle_card_action(
            {"operator": {"open_id": "ou_x"}, "action": {"value": {"bug_id": 1, "action": "hack"}}}, db)
        assert resp["data"]["toast"]["type"] == "error"

    def test_unbound_user(self, db):
        resp = feishu_callback.handle_card_action(
            {"operator": {"open_id": "ou_unknown"}, "action": {"value": {"bug_id": 1, "action": "start"}}}, db)
        assert resp["data"]["toast"]["type"] == "error"
        assert "未绑定" in resp["data"]["toast"]["content"]


# ── apply_bug_transition：service 层（monkeypatch 权限与规则）──────────

class TestApplyBugTransition:
    def _patch_checks(self, monkeypatch, validate_ok: bool = True):
        """绕过 RBAC 与规则表：check_permission 返回 pm，validate 按需放行"""
        import app.services.transition_service as ts
        monkeypatch.setattr(ts, "check_permission", lambda db, uid, pid, code: "pm")
        if validate_ok:
            monkeypatch.setattr(ts, "validate_transition",
                                lambda *a, **k: (True, None))
        else:
            monkeypatch.setattr(ts, "validate_transition",
                                lambda *a, **k: (False, "不允许此流转"))

    def _create_bug(self, db):
        bug = Bug(project_id=1, title="回调测试", reporter_id=db.bound_id,
                  assignee_id=db.bound_id, status=BugStatus.ASSIGNED)
        db.add(bug)
        db.commit()
        db.refresh(bug)
        return bug

    def test_success_transitions_to_in_progress(self, db, monkeypatch):
        self._patch_checks(monkeypatch)
        bug = self._create_bug(db)
        from app.services.transition_service import apply_bug_transition
        updated, old_status = apply_bug_transition(db, bug.id, db.get(User, db.bound_id), BugStatus.IN_PROGRESS)
        assert old_status == BugStatus.ASSIGNED
        assert updated.status == BugStatus.IN_PROGRESS
        # 写了历史记录
        from app.models.bug import BugHistory
        history = db.query(BugHistory).filter(BugHistory.bug_id == bug.id).all()
        assert any(h.field_name == "status" for h in history)

    def test_invalid_transition_raises_403(self, db, monkeypatch):
        self._patch_checks(monkeypatch, validate_ok=False)
        bug = self._create_bug(db)
        from fastapi import HTTPException
        from app.services.transition_service import apply_bug_transition
        with pytest.raises(HTTPException) as exc:
            apply_bug_transition(db, bug.id, db.get(User, db.bound_id), BugStatus.IN_PROGRESS)
        assert exc.value.status_code == 403

    def test_include_extra_fields_written_to_history(self, db, monkeypatch):
        """携带 assignee_id / fix_description 时写入对应历史"""
        self._patch_checks(monkeypatch)
        bug = self._create_bug(db)
        from app.services.transition_service import apply_bug_transition
        updated, _ = apply_bug_transition(
            db, bug.id, db.get(User, db.bound_id), BugStatus.IN_PROGRESS,
            fix_description="修复完成",
        )
        assert updated.fix_description == "修复完成"
        from app.models.bug import BugHistory
        history = db.query(BugHistory).filter(BugHistory.bug_id == bug.id).all()
        assert any(h.field_name == "fix_description" for h in history)
