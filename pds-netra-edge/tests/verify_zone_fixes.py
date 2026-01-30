import sys
import os
from datetime import datetime

# Add app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.cv.zones import point_in_polygon, is_bbox_in_zone
from app.rules.evaluator import RulesEvaluator
from app.rules.loader import UnauthPersonAfterHoursRule

def test_overlapping_zones():
    print("Testing overlapping zones...")
    evaluator = RulesEvaluator(
        camera_id="test_cam",
        godown_id="test_gdn",
        rules=[],
        zone_polygons={
            "outer": [(0, 0), (100, 0), (100, 100), (0, 100)],
            "inner": [(25, 25), (75, 25), (75, 75), (25, 75)]
        },
        timezone="UTC"
    )
    # Manually set scaled polygons since update_zone_polygons is meant for normalized
    evaluator.zone_polygons = {
        "outer": [(0, 0), (100, 0), (100, 100), (0, 100)],
        "inner": [(25, 25), (75, 25), (75, 75), (25, 75)]
    }
    
    bbox_in_both = [40, 40, 60, 60] # Center at 50, 50
    matched = evaluator._determine_zones(bbox_in_both)
    print(f"Matched zones for object in both: {matched}")
    assert "outer" in matched
    assert "inner" in matched
    assert len(matched) == 2

    bbox_in_outer_only = [10, 10, 20, 20] # Center at 15, 15
    matched = evaluator._determine_zones(bbox_in_outer_only)
    print(f"Matched zones for object in outer only: {matched}")
    assert "outer" in matched
    assert "inner" not in matched
    assert len(matched) == 1
    print("Overlap test PASSED.")

def test_resolution_scaling():
    print("Testing resolution scaling (normalization)...")
    evaluator = RulesEvaluator(
        camera_id="test_cam",
        godown_id="test_gdn",
        rules=[],
        zone_polygons={},
        timezone="UTC"
    )
    
    normalized_polygons = {
        "gate": [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)]
    }
    
    # Scale to 1280x720
    evaluator.update_zone_polygons(normalized_polygons, 1280, 720)
    scaled = evaluator.zone_polygons["gate"]
    print(f"Scaled to 1280x720: {scaled}")
    assert scaled == [(128, 72), (256, 72), (256, 144), (128, 144)]
    
    # Scale to 1920x1080
    evaluator.update_zone_polygons(normalized_polygons, 1920, 1080)
    scaled = evaluator.zone_polygons["gate"]
    print(f"Scaled to 1920x1080: {scaled}")
    assert scaled == [(192, 108), (384, 108), (384, 216), (192, 216)]
    
    # Check backward compatibility (absolute pixels)
    mixed_polygons = {
        "old_absolute": [(100, 100), (200, 100), (200, 200), (100, 200)]
    }
    evaluator.update_zone_polygons(mixed_polygons, 1280, 720)
    scaled = evaluator.zone_polygons["old_absolute"]
    print(f"Old absolute preserved: {scaled}")
    assert scaled == [(100, 100), (200, 100), (200, 200), (100, 200)]
    
    print("Resolution scaling test PASSED.")

def test_geometric_accuracy():
    print("Testing geometric accuracy (removed AABB fallback)...")
    # Triangle zone
    polygon = [(0, 0), (100, 0), (0, 100)]
    
    # Bounding box of the triangle is [0, 0, 100, 100]
    # Point at (75, 75) is INSIDE the AABB but OUTSIDE the triangle.
    bbox_outside_but_in_aabb = [70, 70, 80, 80] # Center at 75, 75
    
    result = is_bbox_in_zone(bbox_outside_but_in_aabb, polygon)
    print(f"Object in AABB but outside triangle result: {result}")
    assert result is False
    
    bbox_inside = [10, 10, 20, 20] # Center at 15, 15
    result = is_bbox_in_zone(bbox_inside, polygon)
    print(f"Object inside triangle result: {result}")
    assert result is True
    print("Geometric accuracy test PASSED.")

if __name__ == "__main__":
    try:
        test_overlapping_zones()
        print("-" * 20)
        test_resolution_scaling()
        print("-" * 20)
        test_geometric_accuracy()
        print("-" * 20)
        print("ALL MANUAL TESTS PASSED!")
    except AssertionError as e:
        print(f"TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)