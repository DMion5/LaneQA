import plotly.graph_objects as go

from validators import clean_points, display_lane_id


VALID_COLOR = "#2E8B57"
INVALID_COLOR = "#D7263D"


def create_lane_figure(lanes, lane_status):
    """Create an interactive Plotly lane geometry chart."""
    figure = go.Figure()

    for index, lane in enumerate(lanes):
        if not isinstance(lane, dict):
            continue

        status_key = f"row_{index}"
        status = lane_status.get(status_key, {})
        lane_id = status.get("lane_id", display_lane_id(lane, index))
        issue_types = status.get("issue_types", [])
        is_valid = status.get("is_valid", False)

        valid_points = status.get("valid_points")
        if valid_points is None:
            valid_points, _ = clean_points(lane.get("points", []))

        if len(valid_points) == 0:
            continue

        x_values = [point[0] for point in valid_points]
        y_values = [point[1] for point in valid_points]
        status_text = "Valid" if is_valid else "Invalid"
        issue_text = ", ".join(issue_types) if issue_types else "None"

        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines+markers",
                name=f"{lane_id} ({status_text})",
                line={
                    "color": VALID_COLOR if is_valid else INVALID_COLOR,
                    "width": 4 if is_valid else 5,
                },
                marker={"size": 7},
                hovertemplate=(
                    f"<b>Lane:</b> {lane_id}<br>"
                    f"<b>Status:</b> {status_text}<br>"
                    f"<b>Issues:</b> {issue_text}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        title="Lane Geometry Validation Results",
        xaxis_title="X coordinate",
        yaxis_title="Y coordinate",
        legend_title="Lane status",
        hovermode="closest",
        template="plotly_white",
        height=650,
    )

    figure.update_yaxes(scaleanchor="x", scaleratio=1)
    return figure
