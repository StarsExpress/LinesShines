import pandas as pd


def find_median(series: pd.Series) -> float:
    series = series.dropna()  # Inplace is false to copy input series.
    series.sort_values(inplace=True)

    total = len(series)
    if total % 2 == 1:
        return series.iloc[total // 2]

    return round((series.iloc[(total - 1) // 2] + series.iloc[total // 2]) / 2, 1)
