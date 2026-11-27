"""Compute selection flags from CLI reach the launcher spec."""

import sys

from launcher import __main__ as cli


def test_cli_compute_filters(monkeypatch, capsys):
    captured = {}

    def run(spec):
        captured.update(spec)
        return {"run_id": "test", "cells": []}

    monkeypatch.setattr(cli, "run_campaign", run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["launcher", "--config", "g0", "--compute", "--include-remote", "--include-probe"],
    )
    cli.main()
    assert captured["compute"] is True
    assert captured["include_remote"] is True
    assert captured["include_probe"] is True
    assert "test" in capsys.readouterr().out
