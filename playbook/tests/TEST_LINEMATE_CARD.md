# test_linemate_card.py

> **Add tests here when:** changing the Linemate Card's roster table (`renderLinemateRoster()` in `linemate-card.js`): its columns, the frozen columns, or the "Card" button that opens a teammate's own card.

- **Kind:** browser (Playwright). Renders the real roster table on a detached element with the app's own modules and records, then clicks the buttons.
- **Needs:** Chromium and the seeded database (the `live_server_url` fixture); the tests skip without a browser.
- **Covers:** the header reads Player, Card, Position, Games; the Card header is not sortable; one button per row; three frozen columns; each button hands its own player to the card opener, including teammates of different positions on the line; clicking a button whose card is already open does not open a second card (the real `viewFloatingCard()`); a Player Card for a player at another position than the plot ranks him among his own position.
- **Read mode:** the Read table has the name, position and Card head rows, no sortable or frozen cells; its rows are grouped Metadata, Required Metrics, Bonus Metrics (no Bonus for the OL); a card renders Read by default, Sort shows it again, and the Line Summary is identical in both modes and leaves out Pass Cov Percent. The cards are built from synthetic same-team players because the seeded database has one player per position.
- **No cap:** the roster is uncapped (16 players all show, DL and OL); the source has no "See more"; the size reminder shows at 9+ DL / 7+ OL players and not below; a Read card with 16 players keeps the 760px width, gets `is-wide`, scrolls sideways with a sticky label column and shows the "scroll right" hint; a narrow Read card is not wide; the Line Summary covers every player.
- **Also covers (no browser needed):** the card template titles its roster table "Individual" and its summary "Line Summary", both with the Player Card's section-title style, with the Read | Sort switch on the Individual heading.
- **Season name:** a Season Player Card button reads "Linemates" (the "NFL Alumni" rename is Career-only).
- **Not here:** the gold colour and button size → `TEST_CARD_BUTTONS.md`; that the column is left out of the PNG export (not tested); the Career "NFL Alumni" variant (roster and name) → `TEST_NCAAF_CAREER_PAGE.md`.
- **Known gaps:** the export clone dropping the Card column, the widened PNG for a wide roster, and the layout on the narrowest card, are checked by eye only.
