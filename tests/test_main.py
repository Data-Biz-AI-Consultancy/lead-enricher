"""Tests for the console entry point."""

from __future__ import annotations

from lead_enricher import __main__


def test_main_invokes_uvicorn(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(app_path: str, **kwargs) -> None:
        captured["app_path"] = app_path
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9001")

    __main__.main()

    assert captured["app_path"] == "lead_enricher.app:app"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9001
