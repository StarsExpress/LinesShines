# test_png_delivery.py

> **Add tests here when:** changing `frontend/png-delivery.js` (the download, the share sheet, the "Image ready" bar, Copy) or the places that start an export (`attachCardSave()`, Save Plot's handler).

- **Kind:** browser (Playwright).
- **Needs:** Chromium (skips without it), `live_server_url` with `seeded_db`, and a Player Card opened from the first record.
- **Covers:** on desktop the card is downloaded as a `.png`; the blob URL is not revoked right after the click; the bar says "Preparing image…" during the export and is gone after; a failed export says so and frees the Save button; on a stubbed phone (coarse pointer, `share`, `userActivation`, clipboard): a fresh tap opens the share sheet at once with one PNG file, an expired tap shows "Image ready" and Share / Save shares the file, Copy writes an `image/png` to the clipboard and says "Image copied", Copy is absent without a clipboard that takes images, a refused share falls back to the ready bar, closing the share sheet leaves no bar, and ✕ hides the bar.
- **Not here:** the frame and credit band of the PNG → `TEST_CARD_EXPORT_FRAME.md`; Save Plot's Plotly export (not testable here, see that file).
- **Known gaps:** nothing runs on a real iPhone in CI: `navigator.share`, `userActivation` and the clipboard are stubs. The real share sheet (Save Image, Copy) was checked by hand on an iPhone PWA over HTTPS; over plain `http://` LAN it falls back to a download, so a phone check needs an HTTPS tunnel. Save Plot's new "Preparing image…" and failure path are not exercised.
