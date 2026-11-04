"""Go/no-go verdict of scripts/forecast_backtest.py --readiness (no DB)."""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "forecast_backtest",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "forecast_backtest.py"))
fb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fb)


def _task(auc, lift, skill, prevalence=0.05, n_test=10000):
    base = {"model": "constant base rate", "auc": 0.5, "lift_top5": 1.0,
            "brier_skill_vs_base": 0.0, "prevalence": prevalence}
    best = {"model": "logistic", "auc": auc, "lift_top5": lift,
            "brier_skill_vs_base": skill, "prevalence": prevalence}
    return {"results": [base, best], "n_test": n_test}


def _out(a, b):
    return {"plans_y_drop": a, "floor": b}


def test_not_ready_without_a_full_year_even_with_a_strong_model():
    v = fb.readiness(_out(_task(0.9, 5, 0.2), _task(0.9, 5, 0.2)), history_days=200)
    assert v["verdict"] == "NOT_READY"
    assert v["tasks"]["plans_y_drop"]["passes"]
    assert not v["history_ok"]


def test_ready_when_one_task_clears_every_bar():
    v = fb.readiness(_out(_task(0.75, 3.5, 0.08), _task(0.55, 1.2, -0.1)), history_days=400)
    assert v["verdict"] == "READY"
    assert v["ready_tasks"] == ["plans_y_drop"]


def test_poor_calibration_blocks_a_high_auc():
    v = fb.readiness(_out(_task(0.8, 4, -0.05), _task(0.8, 4, -0.05)), history_days=400)
    assert v["verdict"] == "NOT_READY"
    assert not v["tasks"]["floor"]["checks"]["brier_skill"]


def test_too_few_positives_blocks():
    v = fb.readiness(_out(_task(0.8, 4, 0.1, prevalence=0.001, n_test=1000),
                          _task(0.8, 4, 0.1, prevalence=0.001, n_test=1000)), history_days=400)
    assert v["verdict"] == "NOT_READY"
