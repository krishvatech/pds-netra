from app.cv.zones import point_in_polygon, is_bbox_in_zone


def test_point_in_polygon_basic():
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(5, 5, polygon) is True
    assert point_in_polygon(-1, -1, polygon) is False


def test_is_bbox_in_zone():
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    bbox_inside = [2, 2, 4, 4]
    bbox_outside = [20, 20, 30, 30]
    assert is_bbox_in_zone(bbox_inside, polygon) is True
    assert is_bbox_in_zone(bbox_outside, polygon) is False