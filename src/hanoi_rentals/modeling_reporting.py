"""Read completed experiment artifacts and export English modeling figures/report."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from .eda_audit import ROOT, LABELS, markdown_table


def generate_modeling_report(root=ROOT):
    root = Path(root)
    reports = root / "reports"
    destination = reports / "modeling_figures"
    destination.mkdir(exist_ok=True)
    meta = json.loads((root / "artifacts/model_metadata.json").read_text())
    scores = pd.read_csv(reports / "model_comparison.csv")
    predictions = pd.read_csv(reports / "modeling_predictions.csv")
    subgroups = pd.read_csv(reports / "modeling_subgroups.csv")
    importance = pd.read_csv(reports / "modeling_permutation.csv")
    errors = pd.read_csv(reports / "modeling_error_review.csv").fillna("")
    splits = pd.read_csv(root / "data/analysis/modeling_splits.csv")
    folds = pd.read_csv(reports / "modeling_fold_coverage.csv")
    selected = meta["selected_model"]
    candidate = meta["best_source_free_candidate"]
    selected_pred = predictions[predictions.model.eq(selected)]
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    figures = []

    def save(fig, name, note):
        fig.text(0.01, 0.01, note, fontsize=9)
        fig.tight_layout(rect=(0, 0.09, 1, 0.96))
        path = destination / f"{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        figures.append(path)

    oof = scores[scores.partition.eq("development_oof")]
    top = oof.sort_values("mae_vnd").head(10)
    top = (
        pd.concat(
            [
                top,
                oof[oof.model.isin(["baseline_global", "baseline_category", selected])],
            ]
        )
        .drop_duplicates("model")
        .sort_values("mae_vnd")
    )
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = ["#237E83" if n == selected else "#799DB4" for n in top.model]
    ax.barh(top.model, top.mae_vnd / 1e6, color=colors)
    ax.invert_yaxis()
    ax.set(
        xlabel="Pooled OOF MAE (million VND/month)",
        title="Development comparison — same grouped folds",
    )
    save(
        fig,
        "01_development_comparison",
        "Development scores informed selection; these are not untouched-test estimates. Teal marks the selected model.",
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, part in zip(axes, ["development_oof", "internal_test"]):
        p = selected_pred[selected_pred.partition.eq(part)]
        for cat, g in p.groupby("category"):
            ax.scatter(
                g.actual_vnd / 1e6,
                g.prediction_vnd / 1e6,
                s=16,
                alpha=0.6,
                label=f"{LABELS[cat]} n={len(g)}",
            )
        hi = max(p.actual_vnd.max(), p.prediction_vnd.max()) / 1e6
        ax.plot([0, hi], [0, hi], color="black", ls="--", lw=1)
        ax.set(
            xscale="symlog",
            yscale="symlog",
            xlabel="Actual (million VND/month)",
            ylabel="Predicted (million VND/month)",
            title=f"{part} · n={len(p)}",
        )
        ax.legend(fontsize=8)
    save(
        fig,
        "02_predictions",
        "Selected model. Symmetric-log axes retain zero-clipped predictions. Internal test was previously inspected during EDA.",
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, part in zip(axes, ["development_oof", "internal_test"]):
        p = selected_pred[selected_pred.partition.eq(part)]
        ax.scatter(p.actual_vnd / 1e6, p.residual_vnd / 1e6, alpha=0.5, s=18)
        ax.axhline(0, color="black", lw=1)
        ax.set(
            xscale="log",
            xlabel="Actual asking rent (million VND/month)",
            ylabel="Prediction − actual (million VND/month)",
            title=f"{part} · n={len(p)}",
        )
    save(
        fig,
        "03_residuals",
        "Negative residuals indicate underprediction. Expensive observations are retained; no test-target tail trimming.",
    )
    chosen = subgroups[
        subgroups.partition.eq("internal_test")
        & subgroups.dimension.eq("category")
        & subgroups.model.isin([selected, "baseline_category"])
    ].copy()
    chosen["property_type"] = chosen["group"].map(LABELS)
    chosen["mae_million"] = chosen.mae_vnd / 1e6
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, value, ylabel in zip(
        axes,
        ["mae_million", "nmae_pct"],
        ["MAE (million VND/month)", "Category NMAE (%)"],
    ):
        sns.barplot(
            data=chosen, x="property_type", y=value, hue="model", errorbar=None, ax=ax
        )
        ax.set(xlabel="", ylabel=ylabel, title="Internal test by category")
        ax.tick_params(axis="x", rotation=10)
    count_note = "; ".join(
        f"{LABELS[r.group]} n={r.n}"
        for r in chosen[chosen.model.eq(selected)].itertuples()
    )
    save(
        fig,
        "04_category_errors",
        count_note
        + ". NMAE = category MAE / observed category median; not mean per-listing percentage error.",
    )
    imp = (
        importance.groupby("feature")
        .mae_increase_vnd.agg(["mean", "std"])
        .sort_values("mean")
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(
        imp.index, imp["mean"] / 1e6, xerr=imp["std"] / 1e6, color="#237E83", alpha=0.8
    )
    ax.axvline(0, color="black", lw=1)
    ax.set(
        xlabel="Validation MAE increase (million VND/month)",
        title=f"Permutation diagnostic — {candidate}",
    )
    save(
        fig,
        "05_permutation_importance",
        "Original input columns permuted within validation folds (5 repeats). Bars show mean ± SD, not CI or causal effects.",
    )
    main_cols = [
        "model",
        "partition",
        "n",
        "mae_vnd",
        "rmse_vnd",
        "r2",
        "median_ae_vnd",
        "p90_ae_vnd",
        "improvement_vs_category_baseline_pct",
        "clipping_count",
    ]
    final_scores = scores[scores.partition.eq("internal_test")]
    final = final_scores[final_scores.model.eq(selected)].iloc[0]
    base = final_scores[final_scores.model.eq("baseline_category")].iloc[0]
    dev_selected = oof[oof.model.eq(selected)].iloc[0]
    sections = [
        "# Modeling report — Hanoi rental asking-price estimation",
        f"**Selected model: {selected}.** Internal-test MAE: **{final.mae_vnd / 1e6:.3f} million VND/month**, compared with **{base.mae_vnd / 1e6:.3f} million** for the category-median baseline ({final.improvement_vs_category_baseline_pct:+.1f}% improvement). RMSE: {final.rmse_vnd / 1e6:.3f} million; R²: {final.r2:.3f}. MAE is primary; R² is supplementary.",
        "The internal test comes from a snapshot already inspected in EDA. It was excluded from model fitting and selection, but is not a genuinely unseen external validation sample. Results concern asking rents for eligible listings, not transactions or the entire Hanoi market.",
        "## 1. Data, bounded review and frozen splits",
        meta["bounded_review"],
        f"Eligible input after review: {meta['eligible_n']} listings in {meta['split_groups']} candidate groups. Development: {meta['development_n']}; internal test: {meta['internal_test_n']}. No P1/P99 target trimming. The processed CSV contains apartments and rooms. Review changes were applied through the audit queue.",
        markdown_table(
            splits.groupby(["partition", "category", "source"])
            .agg(n=("listing_id", "size"), groups=("split_group", "nunique"))
            .reset_index()
        ),
        f"Fold policy: `{meta['fold_policy']}`. Balance rule: {meta['fold_balance_rule']} Source coverage was inspected separately. Group isolation takes priority over exact category proportions. Counts and group counts for all train/validation cells are saved in `modeling_fold_coverage.csv`.",
        markdown_table(folds[folds.role.eq("validation")]),
        "## 2. Features, targets and experiment protocol",
        f"Selected input schema: `{meta['feature_schema']}`. Target: positive monthly rent in VND. Selected target transform: `{meta['selected_config']['target']}`. Parameters: `{meta['selected_config']['params']}`.",
        "Numeric medians, missing indicators, one-hot vocabularies and Ridge scaling are fitted on training folds only. Entirely missing numeric columns retain a zero placeholder plus a missing indicator. Bedrooms/furnishing are optional; bathrooms are deferred. A missingness pattern may proxy source even when source itself is excluded.",
        "Predictors use an explicit whitelist. Price fields, target transformations, title, IDs and audit/review flags are excluded. Unknown districts are encoded without crashing and flagged at inference. Unsupported categories, invalid numeric area/counts and unsupported area units are rejected.",
        f"Nonnegative policy: `{meta['clipping_policy']}`. Clipping is inside the persisted estimator. Raw/final predictions and clipping indicators are retained; no observed train/test minimum is used as a floor.",
        "Two baselines were fitted inside each fold. Diagnostics: 8 Ridge and 16 unconstrained Random Forest configurations. Deployable grid: 8 monotonic histogram boosting and 4 monotonic Random Forest configurations with direct/log targets, sharing five grouped folds. Deployable models are fitted separately by category and omit bedrooms when training coverage is below 35%. The leading constrained core configuration was held fixed for B/C feature ablations; source inclusion and deduplicated-training sensitivity remained development-only diagnostics.",
        f"Selection tie policy: {meta['tie_policy']} A candidate qualifies if OOF MAE improves by at least 10% over the category baseline and no category MAE worsens by more than 10%. The baseline is retained otherwise. No metric or population was changed after viewing internal-test errors.",
        "## 3. Development results and selection",
        markdown_table(
            oof.sort_values("mae_vnd")[
                [
                    "model",
                    "feature_set",
                    "target",
                    "mae_vnd",
                    "rmse_vnd",
                    "r2",
                    "fold_mae_std_vnd",
                    "clipping_count",
                    "runtime_seconds",
                ]
            ]
        ),
        f"Best source-free candidate: **{candidate}**. OOF improvement: **{meta['candidate_oof_improvement_pct']:.1f}%**. Practical rule passed: **{meta['candidate_passes_practical_rule']}**. Category MAE changes relative to the baseline (negative is better): `{meta['candidate_category_mae_change_pct']}`.",
        "OOF estimates were used for selection and are development estimates, not unbiased final performance claims. Per-fold SD is descriptive, not a confidence interval.",
        "## 4. Locked internal-test evaluation",
        markdown_table(final_scores[main_cols]),
        "All models in this table use the same test rows. No test-derived tuning, target trimming or post-test refit was performed. R² retains negative values and is undefined for constant targets or fewer than two observations. MAE, RMSE and other absolute errors are in VND/month.",
        "## 5. Subgroup errors and normalized interpretation",
        "Category NMAE is category MAE divided by the observed median price of the same evaluated category rows. It is a descriptive scale diagnostic, not MAPE and not the selection metric. Groups below 10 show counts only; groups of 10–29 are exploratory.",
        markdown_table(
            subgroups[
                subgroups.model.eq(selected) & subgroups.partition.eq("internal_test")
            ]
        ),
        "Development category comparison:",
        markdown_table(
            subgroups[
                subgroups.partition.eq("development_oof")
                & subgroups.dimension.eq("category")
                & subgroups.model.isin([candidate, "baseline_category"])
            ]
        ),
        "## 6. Source and duplicate sensitivity",
        markdown_table(
            oof[
                oof.model.isin(
                    [candidate, "source_diagnostic_D", "dedup_training_sensitivity"]
                )
            ][main_cols]
        ),
        "Source inclusion may capture differences in collection or listing composition rather than transferable property attributes. The source-aware variant is not the main artifact. Duplicate sensitivity changes training membership only; validation membership stays fixed. Candidate groups are not verified unique properties, and reworded reposts may remain undetected.",
        "## 7. Largest development errors and interpretation",
        "These ten records were selected using OOF absolute errors before internal-test scoring. Titles and audit notes support contextual inspection without changing eligibility, models or predictions. Possible remaining commercial-scope contamination limits interpretation and motivates a separately audited future snapshot. Original Vietnamese titles are retained as evidence.",
        markdown_table(
            errors[
                [
                    "listing_id",
                    "category",
                    "actual_vnd",
                    "prediction_vnd",
                    "absolute_error_vnd",
                    "title",
                ]
                + (["error_review"] if "error_review" in errors else [])
            ]
        ),
        "The permutation diagnostic uses original columns on held-out validation folds, keeping each one-hot expansion together. Correlated inputs can substitute for one another; importance is not causal. It explains the leading source-free candidate, even if the practical rule retains a baseline.",
        "## 8. Artifact, reproducibility and limitations",
        "- `artifacts/rental_price_pipeline.joblib` contains input validation, learned preprocessing, target inversion and clipping. It was fitted on development only, not silently refitted on all data. Reloaded predictions were checked against the fitted object.",
        "- `artifacts/model_selection.json` records the decision made before internal-test scoring. `model_metadata.json` records data/code fingerprints, dependency versions, seed and the split policy.",
        "- Rerunning the notebook reuses the frozen experiment when its data/code/dependencies match. It regenerates the report/figures without re-scoring the internal test. A changed snapshot requires a separately documented experiment.",
        "- Remaining source bias, incomplete fields and imperfect duplicate detection limit generalization. The bounded pre-model scope review is subjective CSV-only curation, not verified ground truth.",
        "- Missing-area and unseen-district performance is reported where enough observations exist; unsupported or very small groups do not establish reliable deployment accuracy.",
        "- Predictions are point estimates of asking rent, with no calibrated uncertainty interval. Prefer a genuinely new snapshot for stronger evaluation. Optional cross-source transfer and temporal extensions were not performed in v1.",
        "- The deployment benchmark is frozen and excluded from training, including candidate duplicate peers. It is reused for operational regression checks and has already been inspected; it is not fresh external validation. Future temporal validation remains necessary.",
        "## 9. Figures",
    ]
    for p in figures:
        sections += [f"### {p.stem}", f"![{p.stem}](modeling_figures/{p.name})"]
    path = reports / "modeling_report.md"
    path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return path, figures
