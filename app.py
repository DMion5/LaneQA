import json
from pathlib import Path

import pandas as pd
import streamlit as st

from importers.opendrive import (
    group_issues_by_severity,
    parse_opendrive_xml,
    validate_opendrive_map,
)
from validators import validate_lanes
from visualization import create_lane_figure


SAMPLE_DATA_PATH = Path(__file__).parent / "sample_data" / "lanes_sample.json"


def load_sample_data():
    with SAMPLE_DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_uploaded_json(uploaded_file):
    try:
        return json.loads(uploaded_file.getvalue().decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"The uploaded file is not valid JSON: {exc}") from exc


def parse_uploaded_opendrive(uploaded_file):
    text = uploaded_file.getvalue().decode("utf-8", errors="replace")
    return parse_opendrive_xml(text, source_name=uploaded_file.name)


def normalize_summary(summary, map_name, source_format):
    summary["map_name"] = map_name
    summary["source_format"] = source_format
    summary.setdefault("roads_parsed", 0)
    summary.setdefault("lane_sections_parsed", 0)
    summary.setdefault("lane_records_parsed", summary.get("total_lanes", 0))
    summary.setdefault("drivable_lanes_parsed", 0)
    summary.setdefault("lane_type_counts", {})
    return summary


def build_report(summary, issues, lane_status):
    return {
        "map_name": summary["map_name"],
        "source_format": summary["source_format"],
        "roads_parsed": summary["roads_parsed"],
        "lane_sections_parsed": summary["lane_sections_parsed"],
        "lane_records_parsed": summary["lane_records_parsed"],
        "drivable_lanes_parsed": summary["drivable_lanes_parsed"],
        "issues_by_severity": group_issues_by_severity(issues),
        "summary": summary,
        "issues": issues,
        "lane_status": lane_status,
    }


def load_uploaded_data(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix in {".xodr", ".xml"}:
        opendrive_map = parse_uploaded_opendrive(uploaded_file)
        issues, lane_status, summary = validate_opendrive_map(opendrive_map)
        summary = normalize_summary(
            summary,
            map_name=opendrive_map["map_name"],
            source_format=opendrive_map["source_format"],
        )
        return opendrive_map["lanes"], issues, lane_status, summary

    lanes = parse_uploaded_json(uploaded_file)
    return lanes, None, None, None


def validate_json_lanes(lanes, sharp_turn_threshold, map_name):
    issues, lane_status, summary = validate_lanes(
        lanes,
        sharp_turn_threshold_degrees=sharp_turn_threshold,
    )
    summary = normalize_summary(
        summary,
        map_name=map_name,
        source_format="LaneQA JSON",
    )
    return issues, lane_status, summary


def render_opendrive_summary(summary):
    columns = st.columns(4)
    columns[0].metric("Roads", summary["roads_parsed"])
    columns[1].metric("Lane sections", summary["lane_sections_parsed"])
    columns[2].metric("Lane records", summary["lane_records_parsed"])
    columns[3].metric("Drivable lanes", summary["drivable_lanes_parsed"])

    if summary["lane_type_counts"]:
        st.subheader("Lane Type Counts")
        lane_type_df = pd.DataFrame(
            [
                {"lane_type": lane_type, "count": count}
                for lane_type, count in summary["lane_type_counts"].items()
            ]
        )
        st.dataframe(lane_type_df, use_container_width=True, hide_index=True)


def render_input_reference():
    with st.expander("Input reference"):
        st.markdown("LaneQA JSON expects a list of lane records:")
        st.code(
            """
[
  {
    "lane_id": "L1",
    "points": [[0, 0], [10, 0], [20, 1]],
    "speed_limit": 35
  }
]
""".strip(),
            language="json",
        )
        st.markdown(
            "OpenDRIVE-lite imports `.xodr` lane metadata, lane widths, and "
            "predecessor/successor links. Full road geometry evaluation is not "
            "included."
        )


def main():
    st.set_page_config(
        page_title="LaneQA: HD Map Geometry QA Dashboard",
        layout="wide",
    )

    st.title("LaneQA: HD Map Geometry QA Dashboard")
    st.caption("Geometry and topology validation for lane-level map data.")

    with st.sidebar:
        st.header("Data Source")
        uploaded_file = st.file_uploader(
            "Upload JSON or OpenDRIVE",
            type=["json", "xodr", "xml"],
        )
        use_sample = st.checkbox("Use sample dataset", value=True)

        sharp_turn_threshold = st.slider(
            "Sharp-turn threshold (degrees)",
            min_value=30,
            max_value=170,
            value=110,
            step=5,
        )

        st.header("Checks")
        st.markdown(
            """
            - Lane identifiers
            - Coordinate validity
            - Minimum lane geometry
            - Sharp turn anomalies
            - OpenDRIVE width and topology links
            """
        )

    try:
        if uploaded_file is not None:
            lanes, issues, lane_status, summary = load_uploaded_data(uploaded_file)
            json_map_name = uploaded_file.name
        elif use_sample:
            lanes = load_sample_data()
            issues = lane_status = summary = None
            json_map_name = "Sample lane dataset"
        else:
            st.info("Upload a file or enable the sample dataset to begin.")
            st.stop()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    if not isinstance(lanes, list):
        st.error("Input data must resolve to a list of lane records.")
        st.stop()

    if issues is None:
        issues, lane_status, summary = validate_json_lanes(
            lanes,
            sharp_turn_threshold,
            json_map_name,
        )

    st.caption(f"{summary['source_format']} | {summary['map_name']}")

    metric_columns = st.columns(4)
    metric_columns[0].metric("Total lanes", summary["total_lanes"])
    metric_columns[1].metric("Valid lanes", summary["valid_lanes"])
    metric_columns[2].metric("Invalid lanes", summary["invalid_lanes"])
    metric_columns[3].metric("Issues", summary["total_issues"])

    if summary["source_format"] == "OpenDRIVE-lite":
        render_opendrive_summary(summary)

    st.subheader("Map QA View")
    st.plotly_chart(create_lane_figure(lanes, lane_status), use_container_width=True)

    st.subheader("Issues")
    if issues:
        issues_df = pd.DataFrame(issues, columns=["lane_id", "issue_type", "severity", "details"])
        st.dataframe(issues_df, use_container_width=True, hide_index=True)
    else:
        st.success("No issues detected.")

    report = build_report(summary, issues, lane_status)
    st.download_button(
        label="Download QA report",
        data=json.dumps(report, indent=2),
        file_name="qa_report.json",
        mime="application/json",
    )

    render_input_reference()


if __name__ == "__main__":
    main()
