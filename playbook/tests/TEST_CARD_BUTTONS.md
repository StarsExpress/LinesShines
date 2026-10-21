# test_card_buttons.py

> **Add tests here when:** changing the Save, Fold or Close buttons in the top right of a card (`.card-save-btn`, `.scout-fold`, `.scout-close` in `style.css`), or the gold buttons that open another card (`.merge-row-linemate-toggle`, `.linemate-row-card-btn`): their size, colours or contrast.

- **Kind:** browser-free. Reads the real `frontend/style.css` and checks each rule and the colour variables it uses.
- **Needs:** nothing extra.
- **Covers:** each button is 24 px; the three fills differ; each icon against its fill is at least 4.5:1; each button's edge against the lightest card background (`--turf-700`) is at least 3:1; Save stays black with the light `#f0ede4` outline; the two gold open-a-card buttons are 28 px, use `--open-card-btn`, and keep icon (4.5:1) and edge (3:1) contrast.
- **Not here:** that the PNG export leaves these buttons out, or that the buttons fold and close the card (not tested).
- **Known gaps:** colour-blind appearance and tap-target size on a real phone are checked by eye only.
