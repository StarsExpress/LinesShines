# test_career_members.py

> **Add tests here when:** changing `database/career.py`: who counts as Joined NFL or a Potential Draftee, how the members are rebuilt, or the per-category membership tables.

- **Kind:** pure Python.
- **Needs:** nothing beyond sqlalchemy. It seeds an in-memory sqlite database with synthetic college and NFL rows.
- **Covers:** a college player whose `player_id` is in the NFL table of the same category is Joined NFL; a player in the latest college season and not in the NFL is a Potential Draftee; a player in neither group is not a member; a Joined NFL player in the latest season is not also a Potential Draftee; the latest season is read from the table, so back-filling an old season changes nothing; a rebuild follows the NFL table (a drafted player flips from Potential Draftee to Joined NFL) and replaces the old members; rebuilding twice gives the same members; each category matches only its own NFL table; an empty college table gives no members; an empty NFL table prints the warning to run the NFL ingestion first.
- **Not here:** that only the college ingestion run calls the rebuild, and the four snap columns being read from the workbook -> `TEST_DB_INGESTION.md`; the Career API that merges the members' rows (not built yet).
- **Known gaps:** none recorded.
