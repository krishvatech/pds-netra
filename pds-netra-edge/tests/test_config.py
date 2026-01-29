from app.config import load_settings


def test_load_settings(tmp_path):
    # Copy the sample config into a temporary directory
    import shutil
    import os
    os.environ["GODOWN_ID"] = "GDN_001"
    # Use package file path relative to this test file
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    sample_config = os.path.join(project_root, 'config', 'pds_netra_config.yaml')
    tmp_config = tmp_path / 'config.yaml'
    try:
        shutil.copy(sample_config, tmp_config)
        settings = load_settings(str(tmp_config))
        assert settings.godown_id == 'GDN_001'
        assert settings.timezone == 'Asia/Kolkata'
        assert len(settings.cameras) >= 1
        assert len(settings.rules) == 0

        os.environ["EDGE_RULES_SOURCE"] = "yaml"
        settings_yaml = load_settings(str(tmp_config))
        assert len(settings_yaml.rules) >= 1
    finally:
        os.environ.pop("GODOWN_ID", None)
        os.environ.pop("EDGE_RULES_SOURCE", None)
