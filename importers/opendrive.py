from collections import Counter, defaultdict
import xml.etree.ElementTree as ET


DRIVABLE_LANE_TYPES = {"driving", "entry", "exit", "onRamp", "offRamp", "connectingRamp"}


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _header_metadata(root):
    header = root.find("header")
    if header is None:
        return {}

    return {
        "name": header.get("name"),
        "revMajor": header.get("revMajor"),
        "revMinor": header.get("revMinor"),
        "version": header.get("version"),
        "date": header.get("date"),
        "north": _to_float(header.get("north")),
        "south": _to_float(header.get("south")),
        "east": _to_float(header.get("east")),
        "west": _to_float(header.get("west")),
        "vendor": header.get("vendor"),
    }


def _parse_widths(lane_element):
    widths = []
    for width in lane_element.findall("width"):
        widths.append(
            {
                "sOffset": _to_float(width.get("sOffset")),
                "a": _to_float(width.get("a")),
                "b": _to_float(width.get("b")),
                "c": _to_float(width.get("c")),
                "d": _to_float(width.get("d")),
            }
        )
    return widths


def _parse_lane_link(lane_element, tag_name):
    link = lane_element.find("link")
    if link is None:
        return None

    target = link.find(tag_name)
    if target is None:
        return None

    return target.get("id")


def _lane_identity(road_id, section_index, lane_id):
    return f"road:{road_id}|section:{section_index}|lane:{lane_id}"


def parse_opendrive_xml(xml_text, source_name="uploaded.xodr"):
    """
    Parse the OpenDRIVE fields used by LaneQA.

    Full OpenDRIVE geometry evaluation is outside the importer scope. Parsed
    lane records receive approximate display coordinates for dashboard review.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"The uploaded OpenDRIVE file is not valid XML: {exc}") from exc

    if root.tag != "OpenDRIVE":
        raise ValueError("Expected an OpenDRIVE XML root element.")

    header = _header_metadata(root)
    map_name = header.get("name") or source_name
    lanes = []
    roads = []
    lane_sections = []

    road_elements = root.findall("road")
    for road_index, road in enumerate(road_elements):
        road_id = road.get("id")
        road_name = road.get("name")
        road_length = _to_float(road.get("length"))
        junction_id = road.get("junction")

        roads.append(
            {
                "road_id": road_id,
                "road_name": road_name,
                "road_length": road_length,
                "junction_id": junction_id,
            }
        )

        section_elements = road.findall("./lanes/laneSection")
        for section_index, lane_section in enumerate(section_elements):
            section_s = _to_float(lane_section.get("s"))
            lane_sections.append(
                {
                    "road_id": road_id,
                    "section_index": section_index,
                    "s": section_s,
                }
            )

            for lane_group in ("left", "center", "right"):
                group = lane_section.find(lane_group)
                if group is None:
                    continue

                for lane_order, lane_element in enumerate(group.findall("lane")):
                    raw_lane_id = lane_element.get("id")
                    lane_id_int = _to_int(raw_lane_id)
                    lane_type = lane_element.get("type", "unknown")
                    level = lane_element.get("level")
                    lane_identity = _lane_identity(road_id, section_index, raw_lane_id)

                    # Approximate display coordinates only; OpenDRIVE geometry
                    # evaluation is intentionally not performed here.
                    y_offset = road_index * 12 + section_index * 3
                    if lane_id_int is not None:
                        y_offset += lane_id_int
                    else:
                        y_offset += lane_order

                    start_x = section_s if section_s is not None else 0.0
                    end_x = start_x + (road_length if road_length is not None else 10.0)

                    lanes.append(
                        {
                            "lane_id": lane_identity,
                            "points": [[start_x, y_offset], [end_x, y_offset]],
                            "source_format": "OpenDRIVE-lite",
                            "road_id": road_id,
                            "road_name": road_name,
                            "road_length": road_length,
                            "junction_id": junction_id,
                            "lane_section_index": section_index,
                            "lane_section_s": section_s,
                            "lane_group": lane_group,
                            "opendrive_lane_id": raw_lane_id,
                            "opendrive_lane_id_int": lane_id_int,
                            "lane_type": lane_type,
                            "level": level,
                            "widths": _parse_widths(lane_element),
                            "predecessor_id": _parse_lane_link(lane_element, "predecessor"),
                            "successor_id": _parse_lane_link(lane_element, "successor"),
                        }
                    )

    return {
        "map_name": map_name,
        "source_format": "OpenDRIVE-lite",
        "header": header,
        "roads": roads,
        "lane_sections": lane_sections,
        "lanes": lanes,
    }


def _add_issue(issues, lane, issue_type, severity, details):
    issues.append(
        {
            "lane_id": lane.get("lane_id", "unknown"),
            "issue_type": issue_type,
            "severity": severity,
            "details": details,
        }
    )


def _section_lane_index(lanes):
    section_map = defaultdict(set)
    all_lane_ids = set()
    for lane in lanes:
        lane_id = lane.get("opendrive_lane_id_int")
        if lane_id is None:
            continue
        key = (lane.get("road_id"), lane.get("lane_section_index"))
        section_map[key].add(lane_id)
        all_lane_ids.add(lane_id)
    return section_map, all_lane_ids


def _link_is_broken(lane, link_name, section_map, all_lane_ids):
    link_value = lane.get(link_name)
    if link_value is None:
        return False

    link_id = _to_int(link_value)
    if link_id is None:
        return True

    section_index = lane.get("lane_section_index")
    if link_name == "predecessor_id":
        target_section = section_index - 1
    else:
        target_section = section_index + 1

    same_road_target = (lane.get("road_id"), target_section)
    if same_road_target in section_map:
        return link_id not in section_map[same_road_target]

    # Road-level topology is not evaluated, so terminal sections fall back to a
    # conservative map-wide lane existence check.
    return link_id not in all_lane_ids


def validate_opendrive_map(opendrive_map):
    """Run OpenDRIVE-lite QA checks and return issues, lane status, and summary."""
    lanes = opendrive_map["lanes"]
    issues = []
    lane_status = {}

    identities = [lane.get("lane_id") for lane in lanes]
    duplicate_identities = {
        identity for identity, count in Counter(identities).items() if identity is not None and count > 1
    }
    section_map, all_lane_ids = _section_lane_index(lanes)

    for index, lane in enumerate(lanes):
        issue_types = []
        raw_lane_id = lane.get("opendrive_lane_id")
        lane_type = lane.get("lane_type")
        is_drivable = lane_type in DRIVABLE_LANE_TYPES

        if lane.get("lane_id") in duplicate_identities:
            issue_types.append("duplicate_lane_identity")
            _add_issue(
                issues,
                lane,
                "duplicate_lane_identity",
                "high",
                "same road, lane section, and OpenDRIVE lane id appear more than once",
            )

        if raw_lane_id is None or str(raw_lane_id).strip() == "" or lane.get("opendrive_lane_id_int") is None:
            issue_types.append("invalid_or_missing_lane_id")
            _add_issue(
                issues,
                lane,
                "invalid_or_missing_lane_id",
                "high",
                f"OpenDRIVE lane id is invalid or missing: {raw_lane_id}",
            )

        if is_drivable and not lane.get("widths"):
            issue_types.append("missing_width_for_drivable_lane")
            _add_issue(
                issues,
                lane,
                "missing_width_for_drivable_lane",
                "medium",
                "drivable lane has no width polynomial",
            )

        for link_name, issue_name in (
            ("predecessor_id", "broken_predecessor_reference"),
            ("successor_id", "broken_successor_reference"),
        ):
            if _link_is_broken(lane, link_name, section_map, all_lane_ids):
                issue_types.append(issue_name)
                _add_issue(
                    issues,
                    lane,
                    issue_name,
                    "high",
                    f"{link_name.replace('_id', '')} lane reference '{lane.get(link_name)}' could not be resolved",
                )

        if is_drivable and lane.get("predecessor_id") is None and lane.get("successor_id") is None:
            issue_types.append("isolated_drivable_lane")
            _add_issue(
                issues,
                lane,
                "isolated_drivable_lane",
                "low",
                "drivable lane has neither predecessor nor successor lane link",
            )

        lane_status[f"row_{index}"] = {
            "lane_id": lane["lane_id"],
            "is_valid": len(issue_types) == 0,
            "issue_types": sorted(set(issue_types)),
            "valid_points": lane.get("points", []),
        }

    lane_type_counts = Counter(lane.get("lane_type", "unknown") for lane in lanes)
    drivable_count = sum(1 for lane in lanes if lane.get("lane_type") in DRIVABLE_LANE_TYPES)
    invalid_lanes = sum(1 for status in lane_status.values() if not status["is_valid"])

    summary = {
        "map_name": opendrive_map["map_name"],
        "source_format": opendrive_map["source_format"],
        "roads_parsed": len(opendrive_map["roads"]),
        "lane_sections_parsed": len(opendrive_map["lane_sections"]),
        "lane_records_parsed": len(lanes),
        "drivable_lanes_parsed": drivable_count,
        "lane_type_counts": dict(sorted(lane_type_counts.items())),
        "total_lanes": len(lanes),
        "valid_lanes": len(lanes) - invalid_lanes,
        "invalid_lanes": invalid_lanes,
        "total_issues": len(issues),
    }

    return issues, lane_status, summary


def group_issues_by_severity(issues):
    grouped = {"high": [], "medium": [], "low": []}
    for issue in issues:
        grouped.setdefault(issue.get("severity", "unknown"), []).append(issue)
    return grouped
