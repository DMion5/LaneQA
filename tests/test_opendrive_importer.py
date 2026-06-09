from importers.opendrive import parse_opendrive_xml, validate_opendrive_map


VALID_MINIMAL_XODR = """
<OpenDRIVE>
  <header name="Valid Minimal" revMajor="1" revMinor="4" version="1.00" />
  <road name="Main" length="50.0" id="10" junction="-1">
    <lanes>
      <laneSection s="0.0">
        <center>
          <lane id="0" type="none" level="false" />
        </center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link>
              <successor id="-1" />
            </link>
            <width sOffset="0.0" a="3.5" b="0.1" c="0.0" d="0.0" />
          </lane>
        </right>
      </laneSection>
      <laneSection s="25.0">
        <center>
          <lane id="0" type="none" level="false" />
        </center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link>
              <predecessor id="-1" />
            </link>
            <width sOffset="0.0" a="3.4" b="0.0" c="0.0" d="0.0" />
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
"""


BROKEN_SUCCESSOR_XODR = """
<OpenDRIVE>
  <header name="Broken Successor" />
  <road name="Main" length="25.0" id="1" junction="-1">
    <lanes>
      <laneSection s="0.0">
        <right>
          <lane id="-1" type="driving" level="false">
            <link>
              <successor id="-99" />
            </link>
            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0" />
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
"""


ISOLATED_DRIVABLE_XODR = """
<OpenDRIVE>
  <header name="Isolated Lane" />
  <road name="Main" length="25.0" id="1" junction="-1">
    <lanes>
      <laneSection s="0.0">
        <right>
          <lane id="-1" type="driving" level="false">
            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0" />
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
"""


def test_parse_valid_minimal_opendrive_file():
    parsed = parse_opendrive_xml(VALID_MINIMAL_XODR, source_name="valid.xodr")

    assert parsed["map_name"] == "Valid Minimal"
    assert parsed["source_format"] == "OpenDRIVE-lite"
    assert len(parsed["roads"]) == 1
    assert len(parsed["lane_sections"]) == 2
    assert len(parsed["lanes"]) == 4
    assert parsed["lanes"][1]["road_id"] == "10"
    assert parsed["lanes"][1]["lane_type"] == "driving"


def test_parse_lane_width_attributes():
    parsed = parse_opendrive_xml(VALID_MINIMAL_XODR)
    driving_lane = next(lane for lane in parsed["lanes"] if lane["lane_type"] == "driving")

    assert driving_lane["widths"] == [
        {"sOffset": 0.0, "a": 3.5, "b": 0.1, "c": 0.0, "d": 0.0}
    ]


def test_detect_broken_successor():
    parsed = parse_opendrive_xml(BROKEN_SUCCESSOR_XODR)
    issues, _, summary = validate_opendrive_map(parsed)

    issue_types = {issue["issue_type"] for issue in issues}
    assert "broken_successor_reference" in issue_types
    assert summary["total_issues"] == 1


def test_detect_isolated_drivable_lane():
    parsed = parse_opendrive_xml(ISOLATED_DRIVABLE_XODR)
    issues, _, summary = validate_opendrive_map(parsed)

    issue_types = {issue["issue_type"] for issue in issues}
    assert "isolated_drivable_lane" in issue_types
    assert summary["invalid_lanes"] == 1


def test_generate_valid_qa_summary_report():
    parsed = parse_opendrive_xml(VALID_MINIMAL_XODR)
    issues, lane_status, summary = validate_opendrive_map(parsed)

    assert issues == []
    assert summary["map_name"] == "Valid Minimal"
    assert summary["source_format"] == "OpenDRIVE-lite"
    assert summary["roads_parsed"] == 1
    assert summary["lane_sections_parsed"] == 2
    assert summary["lane_records_parsed"] == 4
    assert summary["drivable_lanes_parsed"] == 2
    assert summary["lane_type_counts"] == {"driving": 2, "none": 2}
    assert all(status["is_valid"] for status in lane_status.values())
