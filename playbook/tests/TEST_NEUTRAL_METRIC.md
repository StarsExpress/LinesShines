# test_neutral_metric.py

> **Add tests here when:** adding or changing a neutral metric (`neutral: true`), or how Player, Comparison (Merge) or Linemate cards show a metric's rank and percentile.

- **Kind:** browser (Playwright) for card rendering; pure Python for the source and CSS checks.
- **Needs:** the live server and Chromium; skipped when Chromium is missing. The cards are rendered on synthetic five-player slices, because the seeded database has one player per position.
- **Covers:** the DL Player Card grouped into Metadata (Games, PR Opp), Required Metrics and Bonus Metrics (Pass Cov Percent, TPS Pass Cov Percent) with headings, and the OL card with no Bonus section; the Linemate Card Line Summary leaving out Pass Cov Percent and TPS Pass Cov Percent; the metric order (axis pickers, Comparison and Linemate cards) putting the bonus metrics last; the grey chip still shows `#rank/N · Nth pct`; highest value ranks #1; other metrics keep their Color Code; the Comparison Card uses the neutral chip; the Linemate Card source uses it; the Player Card line "Pass Cov Percent: drop to coverage frequency on pass plays." right after the Threshold line (hidden when a category has no `card_note`); metadata flags (`neutral`, `higher_is_better: true`, so the axis is not reversed); chip text contrast at least 4.5:1.
- **Not here:** the Color Code thresholds themselves.
- **Known gaps:** the Linemate roster is checked from source, not rendered; the plot axis direction is checked through metadata only.
