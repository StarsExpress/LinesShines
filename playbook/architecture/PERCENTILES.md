# Percentile and rank computation

> **Load when:** computing, displaying, or comparing any percentile or rank.
> Moved verbatim from the former CLAUDE.md "Architecture" section on 2026-10-17; the text is unchanged.
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Percentile pools must be partitioned by exact position, never combined** (`positionPool()`):
this is the one rule every percentile computation in the file (`render()`'s `currentFiltered`,
Merge Card cells, Linemate Card rows and summary) has to respect now that `currentRecords` holds
every position in the category (see item 6 above) — a Guard's percentile has to come out identical
whether Guard or Tackle is the currently selected chart position.

**Rank and percentile use competition ranking, not an arbitrary tiebreak** (`data.js`'s
`rankAndPercentile()`): two players tied on a metric share the same rank (and therefore the same
percentile) rather than one being bumped ahead by insertion order or player-id — ties are
genuinely equal performances and a deterministic-but-arbitrary tiebreak would misrepresent that as
one player outranking the other. This governs every percentile shown anywhere in the app (chart
hover-free scout card stats, Merge Card cells, Linemate Card rows and summary) since they all funnel
through this one function.
