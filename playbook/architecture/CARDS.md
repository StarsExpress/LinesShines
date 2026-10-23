# Pinned Players, Merge Cards, Linemate Cards

> **Load when:** touching workspace.js, merge-card.js, linemate-card.js, scout-card.js, or cards-base.js.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Pinned Players** (`renderPlayerCardsSpace()`):
the persistent Workspace management region, sitting between the filter drawer and `.board` (outside
it deliberately — `.board`'s floating-card positioning math assumes `.chart-panel` sits at its own
top-left). Plot-click and Workspace membership are fully decoupled: clicking a plotted player
(`viewFloatingCard()`) only opens or flashes his floating card, never touches `workspaceSingles`.
The **only** way to add a Single Cards row is the fuzzy-search box at the top of that column
(`addPlayerToSingleCards()`, same style/engine as the Players filter) — it adds the row but does not
open the card; clicking the player's **name** once he's listed pops/flashes his card, same click+flash
behavior as before. Two independent maps back the column split: `workspaceSingles` (a player's
**Single Cards row**) and `scoutCards` (his **floating card**, open or closed) are decoupled on
purpose — closing a floating card's × (`closeScoutCard()`) touches nothing but that DOM node; the
only way to leave the Workspace is the Single Cards row's own **Remove** button
(`removeSingleCard()`), which also closes the floating card if it was open. Rows carry no Merge
action anymore — see Merge Cards below. **Open on a visitor's first visit**, so the feature is seen, then whatever he last chose, remembered in
`localStorage` (`lines-shines:pinned-panel`, `open` / `closed`; unavailable storage means open;
`restorePlayerCardsSpacePanel()` applies it before the section is first shown). Folded, it is a compact bar
(quota counter + a **Manage** button); open, the same button reads **Hide**. The button (the panel has no
×) expands/collapses `.pcs-panel`'s two columns — Single
Cards (add-search + Remove per row) and Merged Cards (Create button + Edit/Dismiss per row) — a
plain expand/collapse panel, not a `<select>`.

**Merge Cards** (`openCreateMergePopup()`/`submitCreateMergePopup()`/`openMergeCard()`/
`renderMergeCardBody()`/`closeMergeCard()`): built via the Merged Cards column's **Create** button,
which opens a popup with its own staged, popup-local selection (`createSelection`, a
`Map<player,record>`, discarded on Cancel) — not the old per-row Merge button (removed). Picking a
6th member is refused inline; the 8-player Workspace quota is checked only once, at **Submit**,
against the resulting **distinct** total (a player already elsewhere in the Workspace costs nothing),
never against the raw popup selection. Submit builds one floating card — in Read layout by default (one column per player, one row per metric;
see "Merge Card layouts" at the end of this file), or Sort layout (one row per player, one
column per metric), **percentile only** (never the raw value or `#rank/N`) — and does not open the
members' individual floating Player Cards (their Single Cards rows are enough; each member gets one
if he doesn't already have one). A global 8-player quota (`MERGE_QUOTA`, `distinctWorkspacePlayers()`
= the union of `workspaceSingles` and every Merge Card's `memberKeys`) hard-caps the whole Workspace
the same way outside Create too (e.g. the Edit popup's `addMergeMember()`). No two merged cards may
share the same membership: `findDuplicateMergeCard()` compares each card's sorted-by-`id`
`memberIdsKey()` (player **id**, not display name) and blocks Submit/add/remove with "This merged
card already exists." when a match is found. A merged card's own floating × (`closeMergeCardFloating()`)
only hides the view — the card survives in `mergeCards` and its Merged Cards row stays clickable to
reopen/refocus it (`reopenOrFocusMergeCard()`), mirroring Single Cards; **Dismiss**
(`closeMergeCard()`) is the only full dissolve, and frees the members' quota slots. The **Edit**
popup (`openMergeEditPopup()`, `#merge-edit-overlay`) is the only way to change an existing card's
membership post-creation — same fuzzy-match input as the Players filter and the Create popup, all
three scoped to `pcsSearchPool()` (the current position pool only, never cross-position); adding an
existing member, a 6th, or a membership that would duplicate another card is blocked with a message,
and removing down to 1 member auto-dissolves the card (only once the popup closes via Done/Escape,
not on the removal click itself) and returns the survivor to Single Cards.

**Linemate Association Cards** (`computeLinemateRoster()`/`computeThreeMRSWA()`/
`openLinemateCard()`): triggered from a linemate-toggle on any Player Card or any Merge Card
member row, keyed by anchor so the same toggle re-fires as a close — this is what makes the
recursion guard (a Linemate Card renders no linemate toggle of its own) trivial rather than
enforced. Roster = same team/season/category, **including same-position linemates**
(`LINEMATE_POSITIONS`), excluding the anchor, filtered to the applied snap threshold, sorted by
snap count descending and capped per category (`LINEMATE_CAP`: 5 for OL, 7 for DL) — dropping the
lowest first, no positional reservation. First 5 show by default; a "See more" control (DL-only in
practice, since the OL cap is 5) reveals the rest, and resets to collapsed on fold→unfold. The
summary block (Min/Median/RSWA/Max per metric, in that column order) is always computed over the
**full capped roster**, regardless of "See more" state — RSWA (Relative Snaps Weighted Average)
weights each linemate's percentile by his own share of the roster's total snaps
(`weight[t] = snaps[t] / sum(snaps)`), so a linemate who played more counts
for more of the summary. **Deliberately uses each linemate's raw, uncapped snap count** — an earlier
version capped a linemate's snaps at the anchor's own snap count (to approximate true overlap), but
this was reversed: a linemate's full snap count is exactly what expresses how lucky or unlucky the
anchor was to share the field with him, so discounting it for the anchor's own missed time would
understate that. Do not reintroduce a cap here. The RSWA column header carries a click-toggled
info popover (`info-popover.js`'s `createInfoPopover()`) spelling this out — swapped in for a plain
hover tooltip so the explanation is reachable on touch devices too; its click handler calls
`e.stopPropagation()` so opening it doesn't also toggle the header's own sort (see below). Every
table in a Linemate Card (roster and Line Summary) and a Merge Card is sortable Excel-style —
click a header to sort ascending, click again to flip, click a different header to reset to
ascending on that column (`table-sort.js`'s `toggleSortState()`/`sortRows()`/
`makeSortableHeader()`) — except a Merge Card's Linemates column, which holds a button, not data.
Sort state (`{ key, dir }`) lives on the card's own entry and survives re-renders (a snap-threshold
refresh, a roster "See more" toggle) but resets on card close; `null`/`undefined` values always
sort last regardless of direction, so a metric with no qualifying pool doesn't scatter through a
ranked column. Both `table-sort.js` and `info-popover.js` are dependency-free leaves specifically
so `linemate-card.js` can import them without acquiring a dependency on `merge-card.js` (or vice
versa) — see item 6 above.

**"Include {player} into tables" toggle** (`entry.includeAnchor`, default off,
`linemateDisplayRoster()`): a checkbox on every Linemate Card that folds the anchor's own row into
the roster table and the Line Summary, turning the card into a full starting-lineup view rather than
just teammates. `computeLinemateRoster()` itself never sees the anchor — the OL/DL cap and the
threshold-qualifying roster-size note (`"N linemates with ≥ X ..."`) stay teammates-only and
unaffected either way. `linemateDisplayRoster()` inserts the anchor into his rank position by the
category's `threshold_field` (the same field `entry.roster` is already sorted descending by), not a
fixed prepend — so toggling on reads as one snap-ranked line, anchor included, rather than the
anchor pinned to a slot regardless of his own snap count; a header click still re-sorts everyone
same as before. Every render call site (roster table, Line Summary, "See more", fold/unfold,
PNG export's `prepareClone`) reads through this one helper instead of `entry.roster` directly, so
toggling always reflects consistently everywhere with no special-casing per call site — PNG export
in particular needs zero toggle-awareness of its own, it just captures whatever
`linemateDisplayRoster()` currently returns. Title swaps to `"{player} & His Linemates"` when on;
rows carry no visual distinction between anchor and teammates, the title alone frames it as one
group. Persists across a threshold-only refresh the same way `seeMore`/`rosterSort` do; a
season/category/position change dissolves the card outright as usual.

**Design rationale for Merge Cards and Linemate Cards**

- **Percentile only.** A Merge Card row shows one percentile per metric, never the raw value or `#rank/N`, because three numbers per metric would
  make the row unreadably wide (the metric count varies by category and has grown). The full detail is one click away on the individual Player Card.
- **Quota.** The 8-player quota governs analytical complexity; Fold/Unfold governs screen space. That is why Linemate Cards do not count
  against the quota.
- **One linemate toggle per merged member**, even when two members are linemates of each other. Never dedupe by team.
- **Why the caps are 5 and 7.** OL 5 is the other four starters plus one backup. DL 7, together with the anchor, is two 4-man rush packages.
  When more players qualify than slots exist, drop the lowest snap counts first and do not reserve slots by position: a 4-man rush is not
  required to be two interior plus two edge, and more snaps mean more genuine opportunity to have shared the field with the anchor.
- **Summary block meaning.** Min is the unit's floor (its weakest link), Median its water level, RSWA the effectively experienced centre,
  and Max its ceiling (its anchor). All four carry equal weight and are identical for OL and DL; the point is the full picture, so no single
  statistic is favoured per line.

**Merge Card layouts: Read and Sort**

- A Merge Card shows the same percentile cells in one of two layouts, switched by a two-button control, **Read | Sort**, with an (i) popover that says sorting needs Sort. The (i) is built the same way as the Teams, Players and axis ones (`createInfoPopover(..., { label: "ⓘ" })`, styled by the shared glyph-only trigger rule in `style.css`); its popup is a two-point bulleted list: Read (players as columns, no sorting) and Sort (players as rows, click a column header to order by that metric). The mode lives on the card entry as
  `entry.mode` next to `entry.sort`, defaults to Read, and survives membership edits, fold/unfold and a close-then-reopen. It is lost with the Workspace on refresh.
- **Sort** is the original layout: one row per player, one column per metric (plus Player, Team, Linemates, Games and the threshold field), every column sortable except Linemates, with the
  Player/Team/Linemates columns frozen on the left (`applyStickyMetaColumns()`). The table scrolls horizontally.
- **Read** turns the table on its side: one column per player, one row per metric. Each player's name, team logo and Linemates button form a head block that stays pinned at the top
  (`.merge-read-frozen`, a sticky `<thead>`); Games and the threshold field are the first two rows, then one row per metric. Nothing sorts in Read. The columns are compact (a 104px label column, so long metric names wrap onto two or three lines, and 114px per player; the player column was 88px at first and was widened 1.3x), and on the desktop layout the
  card itself shrinks to fit its table (at least 340px, at most 720px, which is five players; the mobile layout keeps its own width). So there is no horizontal scroll and no left freeze, and the table scrolls vertically with the card's panel. The card's scroll hint follows the mode (`.is-read` / `.is-sort`).
- **Read follows the current sort.** Both layouts lay the players out in the order `entry.sort` produces, so a sort made in Sort carries straight over into Read, and switching modes never resets it.
- **One model, two layouts.** `merge-table-model.js` (pure, no DOM) builds `{ players, columns }` and turns it into `sortLayout()` or `readLayout()`, which hold exactly the same cells; Read is the transposition of Sort.
  `merge-card.js` builds the DOM for each cell once (`makeDataCell()`) and both renderers use it, so a cell looks and behaves the same in either layout.
- **PNG export is always the Read layout**, whichever mode is on screen, because the Sort layout is too wide to share. The Merge Card's `prepareClone` re-renders the off-screen clone in Read and returns
  `true`, which makes `exportCardPng()` re-fit the clone to its new size; the card on screen is never touched. The Read|Sort switch and the scroll hints are left out of the PNG.


## Opening a player's card from the Linemate Card, and the gold open-a-card buttons

Each row of the Linemate Card's roster table has a **Card** button in its own column, between Player and
Position (`.linemate-row-card-btn`, a `fa-id-card` icon). Clicking it opens that teammate's Player Card, or,
if it is already open, brings it forward and flashes it (`viewFloatingCard()` in `scout-card.js`, the same
behaviour as a Pinned Players entry; it never toggles a card closed). It works for every row, including
teammates of a different position on the line and the anchor's own row when "Include {anchor}" is on.
The Card header is plain text (nothing to sort), and the column is frozen with Player and Position
(`LINEMATE_META_COLUMN_COUNT = 3`). `linemate-card.js` stays a leaf: it does not import `scout-card.js`
(which already imports it); instead `scout-card.js` registers its opener once with
`setPlayerCardOpener(viewFloatingCard)`. The PNG export drops the whole column from the clone, since the
buttons do nothing in a picture. A Player Card still has its own Linemates toggle, so a teammate's card
can lead on to that teammate's own Linemate Card; the Linemate Card itself never opens another Linemate Card.

The Comparison Card's per-row Linemates button (`.merge-row-linemate-toggle`) uses the same solid gold
(`--open-card-btn`, `#d4af5a`, 28 px square) so "gold button = opens a card"; the icon tells which card
(people group = Linemates, id card = player). The Comparison Card's button is not removed from its PNG export.

**A teammate's card after the threshold changes.** A Player Card opened from the Linemate Card may belong to
a player at another position on the line (a DI while the plot shows ED). `reconcileCarriedCards()` in
`filters.js` therefore keeps floating Player Cards and Linemate anchors by `resolveCarriedRecord()`
(`pinned-impact.js`): the player needs a row at any position in `LINEMATE_POSITIONS[category]` that still
meets the threshold, the card's own position winning when two rows qualify. Pinned players are still judged
at the applied position only. A Player Card ranks its player against `positionPool(record.position)`, not
the plot's `currentFiltered`, so a different-position card shows percentiles among his own position (for a
same-position player the two sets are identical). Percentiles shown before this change were all correct: Player Cards only ever sat at the plot's position, and the Linemate Card table always used each teammate's own position pool.
