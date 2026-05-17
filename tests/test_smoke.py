from crypto_market_intel.cli import main


def test_cli_smoke(capsys):
    main([])
    captured = capsys.readouterr()
    assert "scaffold ready" in captured.out


def test_cli_publish_alerts(monkeypatch, capsys, tmp_path):
    def fake_run_publish_alerts(*, limit: int, reports_dir: str, min_importance: float, notify: bool):
        assert limit == 5
        assert reports_dir == str(tmp_path)
        assert min_importance == 0.9
        assert notify is True
        return {
            "alerts": 2,
            "report_path": str(tmp_path / "alerts-demo.md"),
            "min_importance": 0.9,
            "notify_status": "ok",
        }

    monkeypatch.setattr("crypto_market_intel.cli.run_publish_alerts", fake_run_publish_alerts)

    main([
        "publish-alerts",
        "--limit",
        "5",
        "--reports-dir",
        str(tmp_path),
        "--min-importance",
        "0.9",
        "--notify",
    ])

    captured = capsys.readouterr()
    assert "alert publish complete" in captured.out
    assert "alerts=2" in captured.out
    assert "notify_status=ok" in captured.out
