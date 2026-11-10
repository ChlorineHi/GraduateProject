import json
from pathlib import Path

import pandas as pd
import pytest

from urbannoise.scenarios import NoiseHoldout, noise_from_frame, open_scenario, split_time_space_holdout


def _forbid_build_world(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("real_noise called build_world")

    monkeypatch.setattr("urbannoise.world.build_world", boom)
    monkeypatch.setattr("urbannoise.services.build_world", boom)


def test_time_and_space_holdout_does_not_claim_a_city_field(monkeypatch):
    _forbid_build_world(monkeypatch)
    scenario = open_scenario("real_noise")
    summary = scenario.to_summary()
    assert summary["mode"] == "real_noise"
    assert summary["uses_build_world"] is False
    assert summary["fixture_fallback"] is True
    assert summary["full_city_truth"] is False
    assert summary["citywide_field"] is None
    assert summary["example_schema"] is True
    assert "full-city" in summary["disclaimer"]
    holdout = scenario.make_holdout(seed=0)
    frame = holdout.frame
    train = frame[frame["row_id"].isin(holdout.train_ids)]
    complement_ids = list(holdout.hidden_ids) + list(holdout.locked_ids)
    complement = frame[frame["row_id"].isin(complement_ids)]
    time_hold = set(holdout.time_holdout)
    space_hold = set(holdout.space_holdout)
    assert time_hold
    assert space_hold
    assert set(train["time"].astype(str)).isdisjoint(time_hold)
    assert set(train["space_bin"].astype(str)).isdisjoint(space_hold)
    assert set(holdout.train_ids).isdisjoint(holdout.hidden_ids)
    assert set(holdout.train_ids).isdisjoint(holdout.locked_ids)
    assert set(holdout.hidden_ids).isdisjoint(holdout.locked_ids)
    assert set(holdout.train_ids) | set(holdout.hidden_ids) | set(holdout.locked_ids) == set(frame["row_id"].astype(int))
    time_only = complement[complement["time"].astype(str).isin(time_hold) & ~complement["space_bin"].astype(str).isin(space_hold)]
    space_only = complement[~complement["time"].astype(str).isin(time_hold) & complement["space_bin"].astype(str).isin(space_hold)]
    assert len(time_only) > 0
    assert len(space_only) > 0
    again = scenario.make_holdout(seed=0)
    assert again.locked_ids == holdout.locked_ids
    assert again.hidden_ids == holdout.hidden_ids
    report = holdout.evaluate()
    assert report["protocol"] == "time_space_holdout"
    assert report["full_city_truth"] is False
    assert report["citywide_field"] is None
    assert report["indicators_pooled"] is False
    assert "full-city" in report["disclaimer"]
    assert report["n_locked_test"] == len(holdout.locked_ids) > 0
    assert report["mae"] is not None
    assert "truth" not in report


def test_claimed_city_truth_column_is_ignored():
    raw = pd.read_csv(Path(__file__).parent / "fixtures" / "real_noise_schema_example.csv")
    raw["full_city_truth"] = True
    scenario = open_scenario("real_noise", noise_frame=raw)
    assert scenario.to_summary()["full_city_truth"] is False
    assert scenario.make_holdout(seed=1).evaluate()["full_city_truth"] is False
    assert scenario.make_holdout(seed=1).full_city_truth is False


def test_active_sampling_reveals_only_the_hidden_pool():
    scenario = open_scenario("real_noise")
    holdout = scenario.make_holdout(seed=2)
    frame = holdout.frame
    before = holdout.evaluate()["by_indicator"]["laeq"]["prediction"]
    hidden = frame.loc[frame["row_id"] == holdout.hidden_ids[0]].iloc[0]
    revealed = holdout.reveal(time=str(hidden["time"]), grid_id=int(hidden["grid_id"]), indicator=str(hidden["indicator"]))
    assert revealed["revealed"] is True
    assert revealed["reason"] == "hidden_pool"
    assert revealed["db"] == pytest.approx(float(hidden["db"]))
    assert revealed["full_city_truth"] is False
    assert revealed["added_to_training"] is False
    assert holdout.evaluate()["by_indicator"]["laeq"]["prediction"] == pytest.approx(before)

    locked = frame.loc[frame["row_id"] == holdout.locked_ids[0]].iloc[0]
    sealed = holdout.reveal(time=str(locked["time"]), grid_id=int(locked["grid_id"]), indicator=str(locked["indicator"]))
    assert sealed == {
        "revealed": False,
        "db": None,
        "full_city_truth": False,
        "added_to_training": False,
        "reason": "locked_test",
    }
    assert str(locked["db"]) not in json.dumps(sealed)

    train = frame.loc[frame["row_id"] == holdout.train_ids[0]].iloc[0]
    blocked = holdout.reveal(time=str(train["time"]), grid_id=int(train["grid_id"]), indicator=str(train["indicator"]))
    assert blocked["revealed"] is False
    assert blocked["reason"] == "not_in_hidden_pool"
    assert blocked["db"] is None

    absent = holdout.reveal(time="1999-01-01T00:00:00", grid_id=999)
    assert absent["revealed"] is False
    assert absent["reason"] == "not_in_hidden_pool"
    assert absent["db"] is None
    assert holdout.locked_ids  # the sealed test set is still there


def test_locked_labels_do_not_fit_the_model():
    scenario = open_scenario("real_noise")
    original = scenario.make_holdout(seed=3)
    first = original.evaluate()
    mutated = scenario.frame.copy()
    mutated.loc[mutated["row_id"].isin(original.locked_ids), "db"] = mutated["db"] + 30
    second = split_time_space_holdout(mutated, seed=3)
    report = second.evaluate()
    assert second.locked_ids == original.locked_ids
    assert report["by_indicator"]["laeq"]["prediction"] == pytest.approx(first["by_indicator"]["laeq"]["prediction"])
    assert report["mae"] != pytest.approx(first["mae"])
    assert report["full_city_truth"] is False


def test_indicators_are_not_pooled_into_one_noise_index():
    rows = []
    for stamp in ("t0", "t1", "t2", "t3"):
        for x_coord in (0, 1, 2):
            rows.append(
                {
                    "x": x_coord,
                    "y": 0,
                    "time": stamp,
                    "db": 40.0,
                    "indicator": "laeq",
                    "source": "unit_test",
                    "coordinate_system": "fixture_virtual_grid",
                }
            )
            rows.append(
                {
                    "x": x_coord,
                    "y": 0,
                    "time": stamp,
                    "db": 100.0,
                    "indicator": "lmax",
                    "source": "unit_test",
                    "coordinate_system": "fixture_virtual_grid",
                }
            )
    frame = noise_from_frame(pd.DataFrame(rows))
    last = "t3"
    holdout = NoiseHoldout(
        frame,
        train_ids=tuple(int(row_id) for row_id in frame.loc[frame["time"] != last, "row_id"]),
        hidden_ids=(),
        locked_ids=tuple(int(row_id) for row_id in frame.loc[frame["time"] == last, "row_id"]),
        time_holdout=(last,),
        space_holdout=(),
        seed=0,
    )
    report = holdout.evaluate()
    assert report["indicators_pooled"] is False
    assert set(report["by_indicator"]) == {"laeq", "lmax"}
    assert max(report["by_indicator"]["laeq"]["prediction"]) < 50
    assert min(report["by_indicator"]["lmax"]["prediction"]) > 90
    assert report["mae"] is None
    assert report["full_city_truth"] is False


def test_locked_row_blocks_an_ambiguous_hidden_query():
    frame = noise_from_frame(
        pd.DataFrame(
            [
                {"x": 0, "y": 0, "time": "t0", "db": 40.0, "indicator": "laeq", "source": "unit_test", "coordinate_system": "fixture_virtual_grid"},
                {"x": 0, "y": 0, "time": "t0", "db": 100.0, "indicator": "lmax", "source": "unit_test", "coordinate_system": "fixture_virtual_grid"},
                {"x": 1, "y": 0, "time": "t1", "db": 41.0, "indicator": "laeq", "source": "unit_test", "coordinate_system": "fixture_virtual_grid"},
            ]
        )
    )
    holdout = NoiseHoldout(
        frame,
        train_ids=(2,),
        hidden_ids=(0,),
        locked_ids=(1,),
        time_holdout=(),
        space_holdout=(),
        seed=0,
    )
    mixed = holdout.reveal(time="t0", x=0, y=0)
    assert mixed["revealed"] is False
    assert mixed["reason"] == "locked_test"
    assert mixed["db"] is None
    opened = holdout.reveal(time="t0", x=0, y=0, indicator="laeq")
    assert opened["revealed"] is True
    assert opened["db"] == pytest.approx(40.0)
    assert opened["indicator"] == "laeq"
