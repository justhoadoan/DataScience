from hanoi_rentals.registry import evaluate_gate


def inputs():
    candidate = {"n": 432, "mae_vnd": 1_400_000}
    baseline = {"mae_vnd": 2_500_000}
    categories = {
        "can_ho_chung_cu": {"n": 175, "mae_vnd": 2_000_000},
        "nha_tro": {"n": 257, "mae_vnd": 1_000_000},
    }
    quality = {"development_n": 1700, "exclusion_rate": 0.03, "area_missing_rate": 0.3}
    champion = {
        "overall": {"mae_vnd": 1_600_000},
        "categories": {
            "can_ho_chung_cu": {"mae_vnd": 2_100_000},
            "nha_tro": {"mae_vnd": 1_100_000},
        },
    }
    return candidate, baseline, categories, quality, champion


def test_promote_only_when_all_quality_rules_pass():
    assert evaluate_gate(*inputs())["promoted"]


def test_pooled_improvement_cannot_hide_category_regression():
    c, b, groups, q, champion = inputs()
    groups["nha_tro"]["mae_vnd"] = 1_200_000
    decision = evaluate_gate(c, b, groups, q, champion)
    assert not decision["promoted"]
    assert any("regresses" in message for message in decision["reasons"])


def test_crawl_failure_drift_and_insufficient_gain_keep_champion():
    c, b, g, q, champion = inputs()
    q["crawl_errors"] = True
    assert not evaluate_gate(c, b, g, q, champion)["promoted"]
    q["crawl_errors"] = False
    q["area_psi"] = 0.4
    assert not evaluate_gate(c, b, g, q, champion)["promoted"]
    q["area_psi"] = 0
    c["mae_vnd"] = 1_599_000
    assert not evaluate_gate(c, b, g, q, champion)["promoted"]


def test_nan_scores_and_missing_category_cannot_be_promoted():
    c, b, g, q, _ = inputs()
    c["mae_vnd"] = float("nan")
    assert not evaluate_gate(c, b, g, q)["promoted"]
    c["mae_vnd"] = 1_400_000
    g.pop("nha_tro")
    assert not evaluate_gate(c, b, g, q)["promoted"]


def test_behavior_violation_blocks_even_a_more_accurate_candidate():
    c, b, g, q, champion = inputs()
    q["behavior_violations"] = 1
    assert not evaluate_gate(c, b, g, q, champion)["promoted"]


def test_contract_repair_only_relaxes_gain_for_a_demonstrably_broken_champion():
    c, b, g, q, champion = inputs()
    c["mae_vnd"] = champion["overall"]["mae_vnd"] * 1.02
    assert not evaluate_gate(c, b, g, q, champion)["promoted"]
    champion["behavior"] = {"violations": 1}
    assert evaluate_gate(c, b, g, q, champion)["promoted"]
    c["mae_vnd"] = champion["overall"]["mae_vnd"] * 1.11
    assert not evaluate_gate(c, b, g, q, champion)["promoted"]
    c["mae_vnd"] = champion["overall"]["mae_vnd"]
    g["nha_tro"]["mae_vnd"] = champion["categories"]["nha_tro"]["mae_vnd"] * 1.06
    assert not evaluate_gate(c, b, g, q, champion)["promoted"]
