from app.config import load_settings


def test_rules_loaded():
    settings = load_settings('config/pds_netra_config.yaml')
    # Ensure each rule has mandatory fields
    for rule in settings.rules:
        assert rule.id
        assert rule.type
        assert rule.camera_id
        assert rule.zone_id