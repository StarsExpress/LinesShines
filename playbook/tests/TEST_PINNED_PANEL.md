# test_pinned_panel.py

> **Add tests here when:** changing how the Pinned Players panel opens and folds: its first-visit default, the remembered state, or the Hide / Manage button label (`workspace.js`).

- **Kind:** browser (Playwright), a wide viewport because the panel is desktop and tablet only.
- **Needs:** Chromium and the seeded database (`live_server_url`); the tests skip without a browser.
- **Covers:** a first visit starts open with the button reading Hide; folding sets Manage, `aria-expanded` false and a hidden panel, and survives a reload, and so does opening again; with storage blocked the panel still starts open and the button still works.
- **Not here:** what the panel's lists and popups do → `TEST_PINNED_IMPACT.md` covers only the removal rules; the panel contents are not tested.
- **Known gaps:** the chevron rotation and the layout shift (none expected, the button has a fixed width) are checked by eye only.
