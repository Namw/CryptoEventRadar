from crypto_market_intel.cli import main


def test_cli_smoke(capsys):
    main()
    captured = capsys.readouterr()
    assert "scaffold ready" in captured.out
