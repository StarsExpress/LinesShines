"""Preprocess CSV into Excel."""

from preprocessing.front_7 import preprocess_front_7
from preprocessing.offensive_line import preprocess_offensive_line

if __name__ == "__main__":
    preprocess_front_7(2026)
    preprocess_offensive_line(2026)
