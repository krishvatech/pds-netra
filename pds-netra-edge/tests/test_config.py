from app.config import load_settings


def test_load_settings(tmp_path):
    # Copy the sample config into a temporary directory
    import shutil
    import os
    # Use package file path relative to this test file
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    sample_config = os.path.join(project_root, 'config', 'pds_netra_config.yaml')
    tmp_config = tmp_path / 'config.yaml'
    shutil.copy(sample_config, tmp_config)
    settings = load_settings(str(tmp_config))
    assert settings.godown_id == 'GDN_001'
    assert settings.timezone == 'Asia/Kolkata'
    assert len(settings.cameras) == 2
    assert len(settings.rules) >= 2
