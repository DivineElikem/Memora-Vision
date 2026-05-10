from app.services.text import extract_object_keywords, normalize_object_label


def test_extract_object_keywords():
    assert extract_object_keywords("notify me when someone enters with a bag") == ["bag", "person"]


def test_normalize_object_label():
    assert normalize_object_label("Handbag") == "bag"

