import math
from collections import Counter

import numpy as np


def is_valid_point(point):
    """Return True when a point is shaped like [x, y] with numeric values."""
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        return False

    x, y = point
    if x is None or y is None:
        return False

    try:
        x_float = float(x)
        y_float = float(y)
    except (TypeError, ValueError):
        return False

    return math.isfinite(x_float) and math.isfinite(y_float)


def clean_points(points):
    """Split raw points into valid numeric points and invalid point descriptions."""
    valid_points = []
    invalid_points = []

    if not isinstance(points, list):
        return valid_points, ["points field must be a list"]

    for index, point in enumerate(points):
        if is_valid_point(point):
            valid_points.append([float(point[0]), float(point[1])])
        else:
            invalid_points.append(f"point {index}: {point}")

    return valid_points, invalid_points


def calculate_turn_angle(point_a, point_b, point_c):
    """
    Calculate the turn angle between vectors AB and BC in degrees.

    A straight line is 0 degrees. Larger values mean a sharper change in direction.
    Zero-length vectors return None because the angle is not meaningful.
    """
    vector_ab = np.array(point_b) - np.array(point_a)
    vector_bc = np.array(point_c) - np.array(point_b)

    norm_ab = np.linalg.norm(vector_ab)
    norm_bc = np.linalg.norm(vector_bc)

    if norm_ab == 0 or norm_bc == 0:
        return None

    # Dot product formula: cos(theta) = (AB dot BC) / (|AB| * |BC|).
    # Clipping avoids tiny floating-point drift outside [-1, 1].
    cosine = np.dot(vector_ab, vector_bc) / (norm_ab * norm_bc)
    cosine = np.clip(cosine, -1.0, 1.0)
    return math.degrees(math.acos(cosine))


def detect_sharp_turns(valid_points, threshold_degrees):
    """Return descriptions for turns whose angle exceeds the configured threshold."""
    sharp_turns = []

    for index in range(len(valid_points) - 2):
        angle = calculate_turn_angle(
            valid_points[index],
            valid_points[index + 1],
            valid_points[index + 2],
        )

        if angle is None:
            continue

        if angle > threshold_degrees:
            sharp_turns.append(
                f"turn at point {index + 1} is {angle:.1f} degrees "
                f"(threshold {threshold_degrees} degrees)"
            )

    return sharp_turns


def display_lane_id(lane, index):
    """Return a stable label for issue tables even when lane_id is missing."""
    lane_id = lane.get("lane_id") if isinstance(lane, dict) else None
    if lane_id is None or str(lane_id).strip() == "":
        return f"row_{index}"
    return str(lane_id)


def add_issue(issues, lane_id, issue_type, severity, details):
    issues.append(
        {
            "lane_id": lane_id,
            "issue_type": issue_type,
            "severity": severity,
            "details": details,
        }
    )


def validate_lanes(lanes, sharp_turn_threshold_degrees=110):
    """
    Validate lane objects and return issues, per-lane status, and aggregate counts.

    The lane_status keys include row indexes so duplicate or missing IDs can still be
    represented clearly in the UI and report.
    """
    issues = []
    lane_status = {}

    raw_lane_ids = [
        lane.get("lane_id")
        for lane in lanes
        if isinstance(lane, dict) and lane.get("lane_id") is not None and str(lane.get("lane_id")).strip()
    ]
    duplicate_ids = {lane_id for lane_id, count in Counter(raw_lane_ids).items() if count > 1}

    for index, lane in enumerate(lanes):
        status_key = f"row_{index}"
        lane_issues = []

        if not isinstance(lane, dict):
            add_issue(issues, status_key, "invalid_lane_object", "high", "lane entry must be an object")
            lane_status[status_key] = {
                "lane_id": status_key,
                "is_valid": False,
                "issue_types": ["invalid_lane_object"],
                "valid_points": [],
            }
            continue

        lane_label = display_lane_id(lane, index)
        raw_lane_id = lane.get("lane_id")

        if raw_lane_id is None or str(raw_lane_id).strip() == "":
            lane_issues.append("missing_lane_id")
            add_issue(issues, lane_label, "missing_lane_id", "high", "lane_id is missing or empty")

        if raw_lane_id in duplicate_ids:
            lane_issues.append("duplicate_lane_id")
            add_issue(issues, lane_label, "duplicate_lane_id", "medium", f"lane_id '{raw_lane_id}' appears more than once")

        valid_points, invalid_points = clean_points(lane.get("points", []))

        if invalid_points:
            lane_issues.append("invalid_coordinates")
            add_issue(
                issues,
                lane_label,
                "invalid_coordinates",
                "high",
                "; ".join(invalid_points),
            )

        if len(valid_points) < 2:
            lane_issues.append("too_few_points")
            add_issue(
                issues,
                lane_label,
                "too_few_points",
                "high",
                f"lane has {len(valid_points)} valid coordinate point(s); at least 2 are required",
            )

        sharp_turns = detect_sharp_turns(valid_points, sharp_turn_threshold_degrees)
        if sharp_turns:
            lane_issues.append("sharp_turn_anomaly")
            add_issue(
                issues,
                lane_label,
                "sharp_turn_anomaly",
                "medium",
                "; ".join(sharp_turns),
            )

        lane_status[status_key] = {
            "lane_id": lane_label,
            "is_valid": len(lane_issues) == 0,
            "issue_types": sorted(set(lane_issues)),
            "valid_points": valid_points,
        }

    invalid_lanes = sum(1 for status in lane_status.values() if not status["is_valid"])
    summary = {
        "total_lanes": len(lanes),
        "valid_lanes": len(lanes) - invalid_lanes,
        "invalid_lanes": invalid_lanes,
        "total_issues": len(issues),
    }

    return issues, lane_status, summary
