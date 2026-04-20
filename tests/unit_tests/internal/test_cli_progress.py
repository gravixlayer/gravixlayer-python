"""Tests for gravixlayer._cli_progress helpers."""

from gravixlayer._cli_progress import fmt_duration, AGENT_BUILD_PHASE_LABELS, TEMPLATE_BUILD_PHASE_LABELS


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
        assert TEMPLATE_BUILD_PHASE_LABELS["distributing"] == "VERIFYING"
