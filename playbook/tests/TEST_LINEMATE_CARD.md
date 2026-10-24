# test_linemate_card.py

> **Add tests here when:** changing the Linemate Card's roster table (`renderLinemateRoster()` in `linemate-card.js`): its columns, the frozen columns, or the "Card" button that opens a teammate's own card.

- **Kind:** browser (Playwright). Renders the real roster table on a detached element with the app's own modules and records, then clicks the buttons.
- **Needs:** Chromium and the seeded database (the `live_server_url` fixture); the tests skip without a browser.
- **Covers:** the header reads Player, Card, Position, Games; the Card header is not sortable; one button per row; three frozen columns; each button hands its own player to the card opener, including teammates of different positions on the line; clicking a button whose card is already open does not open a second card (the real `viewFloatingCard()`); a Player Card for a player at another position than the plot ranks him among his own position.
- **Also covers (no browser needed):** the card template titles its roster table "Individual" and its summary "Line Summary", both with the Player Card's section-title style.
- **Not here:** the gold colour and button size → `TEST_CARD_BUTTONS.md`; that the column is left out of the PNG export (not tested).
- **Known gaps:** the export clone dropping the Card column, and the layout on the narrowest card, are checked by eye only.
