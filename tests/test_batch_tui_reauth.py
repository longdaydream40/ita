# Copyright (c) 2026 Idp Team Automation.
# iDP 协议作者：@该隐；注册机作者：@朴圣佑。
# 二开请保留版权；二开不保留版权，以后写代码都是bug。

from __future__ import annotations

from lib.batch_tui import _select_reauth_accounts, run_reauth_batch
from lib.config import RuntimeConfig


def test_run_reauth_batch_uses_worker(monkeypatch, tmp_path):
    calls = []

    def fake_reauth_one(*, cfg, provider, sub2api_account, artifact_dir, progress):
        calls.append((sub2api_account["id"], artifact_dir))
        progress("匹配 IDP 账号", {"sub2api_id": sub2api_account["id"], "email": sub2api_account["credentials"]["email"]})
        return {
            "status": "success",
            "sub2api_id": str(sub2api_account["id"]),
            "email": sub2api_account["credentials"]["email"],
            "idp_account_id": 100 + sub2api_account["id"],
        }

    class FakeProvider:
        def __init__(self, cfg):
            self.config = cfg

    monkeypatch.setattr("lib.batch_tui._reauthorize_one", fake_reauth_one)
    monkeypatch.setattr("lib.batch_tui._sub2api_provider", lambda cfg: FakeProvider(cfg))

    cfg = RuntimeConfig(
        idp_token="tok",
        sub2api_url="https://sub.example",
        sub2api_email="admin@example.com",
        sub2api_password="pw",
        sub2api_group="5",
        artifact_dir=tmp_path,
    )
    accounts = [
        {"id": 1, "credentials": {"email": "a@example.com"}},
        {"id": 2, "credentials": {"email": "b@example.com"}},
    ]
    summary = run_reauth_batch(cfg, accounts=accounts, total_accounts=10, detected_error_count=2, threads=2, artifact_root=tmp_path, retries=1)
    assert summary["mode"] == "reauth"
    assert summary["success_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["sub2api_group_total"] == 10
    assert sorted(item[0] for item in calls) == [1, 2]


def test_reauth_worker_remote_reconcile_success(monkeypatch, tmp_path):
    from lib.batch_tui import _run_reauth_one
    import queue

    class FakeProvider:
        config = object()

        def get_account(self, account_id):
            return {
                "id": int(account_id),
                "status": "active",
                "error_message": "",
                "credentials": {"email": "a@example.com", "expires_at": 123},
            }

    def fail_reauth_one(**kwargs):
        from lib.errors import Sub2ApiError

        raise Sub2ApiError("Too many requests", stage="sub2api_request")

    monkeypatch.setattr("lib.batch_tui._reauthorize_one", fail_reauth_one)
    monkeypatch.setattr("lib.batch_tui._sub2api_provider", lambda cfg: FakeProvider())
    events = queue.Queue()
    cfg = RuntimeConfig(idp_token="tok", sub2api_url="https://sub.example", sub2api_email="e", sub2api_password="p", sub2api_group="5")
    _run_reauth_one(1, {"id": 1, "credentials": {"email": "a@example.com"}}, cfg, tmp_path, events, retries=1)
    kinds = []
    while not events.empty():
        kinds.append(events.get()["type"])
    assert kinds[-1] == "success"


def test_select_reauth_accounts_by_email(monkeypatch):
    class FakeProvider:
        def __init__(self, cfg):
            self.config = cfg

    class FakeScanner:
        def __init__(self, provider):
            self.provider = provider

        def list_accounts(self, *, group):
            return [
                {"id": 1, "status": "error", "credentials": {"email": "a@example.com"}},
                {"id": 2, "status": "error", "credentials": {"email": "b@example.com"}},
            ]

    monkeypatch.setattr("lib.batch_tui._sub2api_provider", lambda cfg: FakeProvider(cfg))
    monkeypatch.setattr("lib.batch_tui.Sub2ApiHealthScanner", FakeScanner)
    cfg = RuntimeConfig(
        idp_token="tok",
        sub2api_url="https://sub.example",
        sub2api_email="admin@example.com",
        sub2api_password="pw",
        sub2api_group="5",
    )
    selected, total, detected = _select_reauth_accounts(cfg, email="b@example.com", progress=False)
    assert total == 2
    assert detected == 1
    assert selected[0]["id"] == 2
