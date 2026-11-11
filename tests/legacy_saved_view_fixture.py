"""Build/read a historical configuration solely to exercise recovery upgrades."""


def add_legacy_saved_view(database, name="Old view", *, tags=()):
    with database.transaction() as connection:
        identifier = connection.execute(
            """INSERT INTO saved_views
            (display_name, normalized_name, search_text, match_mode, include_superseded,
             tag_match_mode, date_meaning, sort)
            VALUES (?, ?, '', 'all', 0, 'all', 'created', 'created_newest')""",
            (name, name.casefold()),
        ).lastrowid
        for tag in tags:
            tag_id = connection.execute(
                "SELECT id FROM tags WHERE normalized_name = ?", (tag.casefold(),)
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO saved_view_tags VALUES (?, ?)", (identifier, tag_id)
            )
        return identifier


def count_legacy_saved_views(database):
    with database.read_snapshot() as connection:
        return connection.execute("SELECT COUNT(*) FROM saved_views").fetchone()[0]
