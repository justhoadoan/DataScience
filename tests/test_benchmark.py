import pandas as pd

from hanoi_rentals.eda_audit import prepare_analysis
from hanoi_rentals.modeling import modeling_population, make_splits
from test_eda import row


def test_new_duplicate_of_benchmark_never_enters_training(tmp_path):
    raw = pd.DataFrame(
        [
            row(
                listing_id=f"id{i}",
                url=f"https://example.test/{i}",
                title=f"Cho thuê căn hộ sạch thoáng khu vực Cầu Giấy số {i}",
            )
            for i in range(90)
        ]
    )
    data = prepare_analysis(raw)
    data.loc[:1, "split_group"] = "same-property-candidate"
    folder = tmp_path / "data/analysis"
    folder.mkdir(parents=True)
    data.to_csv(folder / "listings_analysis.csv", index=False)
    benchmark = tmp_path / "data/benchmark"
    benchmark.mkdir()
    pd.DataFrame({"listing_id": ["id0"]}).to_csv(benchmark / "ids.csv", index=False)
    population = modeling_population(tmp_path)
    assert "id1" not in set(population.listing_id)
    assert "id0" in set(population.listing_id)
    splits, _ = make_splits(population, {"id0"})
    assert set(splits.loc[splits.partition.eq("internal_test"), "listing_id"]) == {
        "id0"
    }
    assert set(
        splits.loc[splits.partition.eq("development"), "split_group"]
    ).isdisjoint(set(splits.loc[splits.partition.eq("internal_test"), "split_group"]))
