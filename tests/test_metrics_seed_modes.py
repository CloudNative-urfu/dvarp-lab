"""Seed-level break-even and explicit local/remote metric partitions."""

import pytest
from sqlalchemy import create_engine, text

from .conftest import make_raw, record_turn


def test_existing_metric_rows_are_not_mislabelled_local(lab_env):
    from services.metrics import app as metrics_app

    engine = create_engine(f"sqlite:///{lab_env.metrics_db}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE metric_results (id INTEGER PRIMARY KEY, config_name VARCHAR(128), "
                "model_spec TEXT, metric VARCHAR(128), value TEXT, computed_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO metric_results (config_name, model_spec, metric, value, computed_at) "
                "VALUES ('g0', '{}', 'V', '0', CURRENT_TIMESTAMP)"
            )
        )
    metrics_app.init_metrics_db()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT mode FROM metric_results")).scalar_one() == "all"


async def _episode(client, config, seed, channel, *, violation=False, remote=False):
    await record_turn(
        client,
        config_name=config,
        episode_id=f"campaign-{config}-{seed}-{channel}",
        channel=channel,
        raw=make_raw(
            config_name=config,
            verdict={
                "violation": violation,
                "outcome": "executed" if violation else "refused",
                "task_status": "completed",
                "escalated": False,
            },
            extra={"run_id": "campaign", "seed": seed, "remote_llm": remote},
        ),
    )


async def test_seed_spread_uses_run_and_seed_and_matching_reference(filter_client, metrics_client):
    for seed, ref_violation, guarded_violation in ((1, True, False), (2, False, True)):
        for config, violation in (("g0", ref_violation), ("g_proc", guarded_violation)):
            await _episode(filter_client, config, seed, "attack", violation=violation)
            await _episode(filter_client, config, seed, "legal")

    preview = (await metrics_client.post("/preview", json={"config_name": "g_proc"})).json()
    group = preview["groups"][0]
    spread = group["final"]["seed_spread"]
    assert group["seed_spread"] == spread
    assert spread["runs"] == 2
    assert [(r["run_id"], r["seed"]) for r in spread["groups"]] == [
        ("campaign", 1),
        ("campaign", 2),
    ]
    assert [r["status"] for r in spread["groups"]] == ["pays_at_any_price", "more_violations"]
    assert [r["V"] for r in spread["groups"]] == [0.0, 1.0]
    assert spread["status_stable"] is False
    assert spread["L_star"]["values"] == [pytest.approx(0.0)]

    await metrics_client.post("/compute", json={"config_name": "g_proc"})
    rows = (await metrics_client.get("/metrics/g_proc")).json()["results"]
    assert next(r["value"] for r in rows if r["metric"] == "seed_spread") == spread


async def test_seed_reference_must_match_run_and_seed(filter_client, metrics_client):
    for config, seed in (("g0", 1), ("g_proc", 1), ("g_proc", 2)):
        await _episode(filter_client, config, seed, "attack", violation=config == "g0")
        await _episode(filter_client, config, seed, "legal")
    spread = (await metrics_client.post("/preview", json={"config_name": "g_proc"})).json()[
        "groups"
    ][0]["seed_spread"]
    assert [r["status"] for r in spread["groups"]] == ["pays_at_any_price", "no_reference"]
    assert spread["groups"][1]["L_star"] is None


async def test_compute_separates_modes_and_reports_remote_counts(filter_client, metrics_client):
    for remote in (False, True):
        await record_turn(
            filter_client,
            config_name="g0",
            episode_id=f"g0-{remote}",
            channel="attack",
            raw=make_raw(
                verdict={"violation": remote},
                extra={"remote_llm": remote},
            ),
        )
    await metrics_client.post("/compute", json={"config_name": "g0"})
    rows = (await metrics_client.get("/metrics/g0")).json()["results"]
    assert {r["mode"] for r in rows} == {"local"}
    assert next(r["value"] for r in rows if r["metric"] == "n_remote") == 0

    await metrics_client.post("/compute", json={"config_name": "g0", "include_remote": True})
    rows = (await metrics_client.get("/metrics/g0")).json()["results"]
    values = {(r["mode"], r["metric"]): r["value"] for r in rows}
    assert {
        (mode, values[mode, "n_attack"], values[mode, "n_remote"])
        for mode in ("local", "remote", "all")
    } == {("local", 1, 0), ("remote", 1, 1), ("all", 2, 1)}
    preview = (await metrics_client.post("/preview", json={"include_remote": True})).json()
    assert {g["mode"] for g in preview["groups"]} == {"local", "remote", "all"}
