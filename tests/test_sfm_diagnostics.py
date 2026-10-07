import sqlite3

from floorplan.sfm import _matching_diagnostics, _reconstruction_guidance


MAX_IMAGE_ID = 2_147_483_647


def _pair_id(image_a: int, image_b: int) -> int:
    return min(image_a, image_b) * MAX_IMAGE_ID + max(image_a, image_b)


def _database(path, pairs=()):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute(
            "CREATE TABLE two_view_geometries (pair_id INTEGER PRIMARY KEY, rows INTEGER, config INTEGER)"
        )
        connection.executemany(
            "INSERT INTO images (image_id, name) VALUES (?, ?)",
            [(1, "a.jpg"), (2, "b.jpg"), (3, "c.jpg"), (4, "d.jpg")],
        )
        geometry_rows = []
        for pair in pairs:
            a, b, count, *config = pair
            geometry_rows.append((_pair_id(a, b), count, config[0] if config else 3))
        connection.executemany(
            "INSERT INTO two_view_geometries (pair_id, rows, config) VALUES (?, ?, ?)",
            geometry_rows,
        )


def test_matching_diagnostics_reports_pair_support_and_unpaired_images(tmp_path):
    database = tmp_path / "features.db"
    _database(database, [(1, 2, 50), (2, 3, 20)])

    diagnostics = _matching_diagnostics(database, image_count=4)

    assert diagnostics["candidate_image_pairs"] == 6
    assert diagnostics["geometrically_verified_pair_count"] == 2
    assert diagnostics["verified_pair_fraction"] == 2 / 6
    assert diagnostics["max_verified_inliers"] == 50
    assert diagnostics["median_verified_inliers"] == 35
    assert diagnostics["images_without_verified_pairs"] == ["d.jpg"]
    assert diagnostics["strongest_verified_pairs"][0] == {
        "image_a": "a.jpg",
        "image_b": "b.jpg",
        "verified_inliers": 50,
        "geometry_configuration": "UNCALIBRATED",
    }
    assert diagnostics["verified_geometry_configurations"] == {"UNCALIBRATED": 2}


def test_matching_diagnostics_labels_planar_and_unknown_configurations(tmp_path):
    database = tmp_path / "features.db"
    _database(database, [(1, 2, 50, 6), (2, 3, 40, 42)])

    diagnostics = _matching_diagnostics(database, image_count=4)

    assert diagnostics["verified_geometry_configurations"] == {
        "PLANAR_OR_PANORAMIC": 1,
        "UNKNOWN_42": 1,
    }
    assert diagnostics["strongest_verified_pairs"][0]["geometry_configuration"] == "PLANAR_OR_PANORAMIC"


def test_matching_diagnostics_reports_complete_pair_graph(tmp_path):
    database = tmp_path / "features.db"
    _database(database, [(1, 2, 10), (1, 3, 11), (1, 4, 12),
                         (2, 3, 13), (2, 4, 14), (3, 4, 15)])

    diagnostics = _matching_diagnostics(database, image_count=4)

    assert diagnostics["candidate_image_pairs"] == 6
    assert diagnostics["geometrically_verified_pair_count"] == 6
    assert diagnostics["verified_pair_fraction"] == 1.0
    assert diagnostics["images_without_verified_pairs"] == []


def test_matching_diagnostics_empty_database_and_failure_guidance(tmp_path):
    database = tmp_path / "features.db"
    _database(database)
    diagnostics = _matching_diagnostics(database, image_count=4)

    assert diagnostics["geometrically_verified_pair_count"] == 0
    assert diagnostics["images_without_verified_pairs"] == ["a.jpg", "b.jpg", "c.jpg", "d.jpg"]
    message = _reconstruction_guidance(
        {"registered_images": 0}, diagnostics, image_count=4
    )
    assert "No image pair passed geometric verification" in message


def test_verified_pairs_without_a_model_get_parallax_guidance():
    diagnostics = {"geometrically_verified_pair_count": 1}
    message = _reconstruction_guidance(
        {"registered_images": 0}, diagnostics, image_count=2
    )

    assert "could not initialize a stable 3D model" in message
    assert "parallax" in message
