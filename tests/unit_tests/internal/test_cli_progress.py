"""Tests for gravixlayer._cli_progress helpers."""

from gravixlayer._cli_progress import (
    AGENT_BUILD_PHASE_LABELS,
    TEMPLATE_BUILD_PHASE_LABELS,
    display_phase_label,
    fmt_duration,
    next_display_stage,
)


class TestFmtDuration:
    def test_seconds_only(self):
        assert fmt_duration(12.3) == "12.3s"

    def test_minutes(self):
        assert "m" in fmt_duration(125.0)


class TestPhaseLabelMaps:
    def test_agent_labels_non_empty(self):
        assert AGENT_BUILD_PHASE_LABELS["building"] == "BUILDING"
        assert "completed" in AGENT_BUILD_PHASE_LABELS

    def test_template_labels_non_empty(self):
        assert TEMPLATE_BUILD_PHASE_LABELS["building"] == "BUILDING"
        assert TEMPLATE_BUILD_PHASE_LABELS["uploading"] == "VERIFYING"
        assert TEMPLATE_BUILD_PHASE_LABELS["distributing"] == "VERIFYING"


class TestNextDisplayStage:
    def test_forward_only_ignores_building_after_verifying(self):
        assert next_display_stage("", "building") == "BUILDING"
        assert next_display_stage("BUILDING", "uploading") == "VERIFYING"
        assert next_display_stage("VERIFYING", "building") is None
        assert next_display_stage("VERIFYING", "preparing") is None
        assert next_display_stage("VERIFYING", "finalizing") is None
        assert next_display_stage("VERIFYING", "distributing") is None
        assert next_display_stage("VERIFYING", "completed") is None

    def test_ready_is_not_a_spinner_stage(self):
        assert display_phase_label("completed") == "READY"
        assert next_display_stage("BUILDING", "completed") is None
        assert next_display_stage("", "completed") is None

    def test_unknown_phase_after_known_stage_is_ignored(self):
        assert next_display_stage("VERIFYING", "snapshot") is None
        assert next_display_stage("", "custom") == "CUSTOM"
