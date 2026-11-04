# test_volume_column.py

> **Add tests here when:** changing the Volume column on the Player Card's Required Metrics (which rates get a count, the `volume` key in the metric metadata, the `Volume | Rate` header), or where else a count may or may not appear.

- **Kind:** browser (Playwright).
- **Needs:** the live server and Chromium; skipped when Chromium is missing. Cards are rendered on synthetic five-player slices with every count set to a known number.
- **Covers:** each front 7 rate showing its count beside it (Win Rate with Wins, Pressure Rate with Pressures, Havoc Rate with Havoc, and the TPS twins); PRP, TPS PRP, PBE and the Bonus rows carrying a dash in the Volume cell; the OL showing Pressures, Havoc and `TPS Non Spike PB Snaps` (the last for `TPS Proportion %`); the `Volume | Rate` header only on Required Metrics; the Volume never being a ranked chip while the row labels stay the metrics alone; a missing count showing the same dash; Metadata keeping the denominators, as a one-row table with gridlines and no rank cells (the OL's long labels wrap inside their cells); the Comparison Card having no Volume column; the Player Card dropping the trailing "%" and "Rate" from metric names (and only there: the metadata keeps the full names).
- **Not here:** the `volume` key and the stored counts in the API payloads -> `TEST_API_ENDPOINTS.md`; the counts summed over seasons on Career -> `TEST_CAREER_MERGE.md`; the counts in the workbook and the database -> `TEST_PREPROCESSING_LEAGUE.md`, `TEST_DB_INGESTION.md`.
- **Known gaps:** the column widths and a phone-width layout are not checked, only the cells; the card width (420px) is not asserted.
