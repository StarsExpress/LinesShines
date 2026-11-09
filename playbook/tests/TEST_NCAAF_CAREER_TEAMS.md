# test_ncaaf_career_teams.py

> **Add tests here when:** changing how the NCAAF Career Teams checklist groups schools or how the Career chart lights a team (`teamGroups()`, `populateTeamsChecklist()`, `careerTeamKey()`, `teamKeyOfRecord()`, the `team_conferences` shape in `/api/ncaaf/career/metadata`).

- **Kind:** browser (Playwright).
- **Needs:** Chromium (skips without it), `live_server_url`, and the file's own `seeded_split_conference_db` (four members: Latu and a later UCLA member, Broughton and an earlier Texas member).
- **Covers:** a school whose members last played in two conferences is listed under each (UCLA under Pac-12 and B1G, Texas under Big 12 and SEC); Career opens with nothing ticked; ticking UCLA in one conference leaves UCLA in the other alone; a conference header selects only its own entries; Laiatu Latu (last year 2023) is lit by UCLA in the Pac-12 and not by UCLA in the B1G, and a 2025 UCLA member the other way round; Vernon Broughton (last year 2024) is lit by Texas in the SEC and not the Big 12, and a 2023 Texas member the other way round; the Teams summary naming the school of a single entry.
- **Not here:** the merge itself and the metadata payload -> `TEST_CAREER_MERGE.md`; the season checklists -> `TEST_NCAAF_TEAMS_CHECKLIST.md`; the page's sliders and Status Filter -> `TEST_NCAAF_CAREER_PAGE.md`.
- **Known gaps:** none known.
