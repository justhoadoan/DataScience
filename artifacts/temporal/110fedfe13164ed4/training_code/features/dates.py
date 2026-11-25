"""One calendar contract for observed prices and server-generated valuation dates."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
EPOCH = date(2025, 11, 1)
TARGET_END = date(2026, 12, 31)
HOLDOUT_START = date(2026, 12, 1)


def today_hanoi():
    return datetime.now(ZONE).date()


def parse_dates(values):
    values = pd.Series(np.asarray(values).reshape(-1))
    if not values.map(lambda value: isinstance(value, str)).all():
        raise ValueError("valuation_date requires an explicit ISO date (YYYY-MM-DD).")
    if not values.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("valuation_date requires an explicit ISO date (YYYY-MM-DD).")
    return pd.to_datetime(values, format="%Y-%m-%d", errors="raise")


class DateFeatures(TransformerMixin, BaseEstimator):
    """Fixed epoch and optional circular calendar month; no learned target statistics."""

    def __init__(self, seasonal=True):
        self.seasonal = seasonal

    def fit(self, X, y=None):
        self.transform(X)
        self.n_features_in_ = 1
        return self

    def transform(self, X):
        dates = parse_dates(X)
        elapsed = (dates - pd.Timestamp(EPOCH)).dt.days.to_numpy(dtype=float)
        if not self.seasonal:
            return elapsed.reshape(-1, 1)
        angle = 2 * np.pi * (dates.dt.month.to_numpy() - 1) / 12
        return np.column_stack([elapsed, np.sin(angle), np.cos(angle)])

    def get_feature_names_out(self, input_features=None):
        return np.array(
            ["elapsed_days", "month_sin", "month_cos"]
            if self.seasonal
            else ["elapsed_days"]
        )
