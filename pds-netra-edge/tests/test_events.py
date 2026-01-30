from app.models.event import EventModel, MetaModel, HealthModel


def test_event_model_serialisation():
    meta = MetaModel(zone_id='z1', rule_id='r1', confidence=0.9)
    event = EventModel(
        godown_id='GDN_SAMPLE',
        camera_id='CAM1',
        event_id='uuid',
        event_type='TEST',
        severity='info',
        timestamp_utc='2026-01-20T12:00:00Z',
        bbox=[0, 0, 10, 10],
        track_id=1,
        image_url=None,
        clip_url=None,
        meta=meta,
    )
    json_str = event.json()
    assert 'GDN_SAMPLE' in json_str
    assert 'bbox' in json_str
    assert 'meta' in json_str


def test_health_model_serialisation():
    health = HealthModel(
        godown_id='GDN_SAMPLE',
        device_id='DEV1',
        status='OK',
        online_cameras=2,
        total_cameras=2,
        timestamp_utc='2026-01-20T12:00:00Z',
    )
    json_str = health.json()
    assert 'DEV1' in json_str
    assert 'online_cameras' in json_str