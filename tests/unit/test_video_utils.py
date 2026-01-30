"""
Unit tests for video utility functions.

Tests pure functions from app.services.video_service that have no external dependencies.
These tests focus on:
- ISO8601 duration parsing
- YouTube Shorts text cue detection
- Shorts classification logic
- Thumbnail URL selection
"""

import pytest
from app.services.video_service import (
    parse_iso8601_duration,
    _has_shorts_text_cues,
    _classify_is_short,
    _get_best_thumbnail_url,
)


class TestParseISO8601Duration:
    """Tests for ISO 8601 duration parsing (e.g., PT4M13S -> 253 seconds)."""

    @pytest.mark.unit
    def test_parse_hours_minutes_seconds(self):
        """Should parse full duration with hours, minutes, and seconds."""
        assert parse_iso8601_duration("PT1H30M45S") == 5445

    @pytest.mark.unit
    def test_parse_minutes_only(self):
        """Should parse duration with only minutes."""
        assert parse_iso8601_duration("PT5M") == 300

    @pytest.mark.unit
    def test_parse_seconds_only(self):
        """Should parse duration with only seconds."""
        assert parse_iso8601_duration("PT30S") == 30

    @pytest.mark.unit
    def test_parse_hours_only(self):
        """Should parse duration with only hours."""
        assert parse_iso8601_duration("PT1H") == 3600

    @pytest.mark.unit
    def test_parse_hours_and_minutes(self):
        """Should parse duration with hours and minutes."""
        assert parse_iso8601_duration("PT2H15M") == 8100

    @pytest.mark.unit
    def test_parse_hours_and_seconds(self):
        """Should parse duration with hours and seconds (no minutes)."""
        assert parse_iso8601_duration("PT1H5S") == 3605

    @pytest.mark.unit
    def test_parse_minutes_and_seconds(self):
        """Should parse duration with minutes and seconds."""
        assert parse_iso8601_duration("PT4M13S") == 253

    @pytest.mark.unit
    def test_parse_single_digit_values(self):
        """Should parse single digit values correctly."""
        assert parse_iso8601_duration("PT3M2S") == 182

    @pytest.mark.unit
    def test_parse_boundary_values(self):
        """Should parse boundary values like 59M59S."""
        assert parse_iso8601_duration("PT59M59S") == 3599

    @pytest.mark.unit
    def test_parse_empty_duration_p0d(self):
        """Should return 0 for P0D (zero duration)."""
        assert parse_iso8601_duration("P0D") == 0

    @pytest.mark.unit
    def test_parse_zero_seconds(self):
        """Should return 0 for PT0S."""
        assert parse_iso8601_duration("PT0S") == 0

    @pytest.mark.unit
    def test_parse_none_duration(self):
        """Should return 0 for None input."""
        assert parse_iso8601_duration(None) == 0

    @pytest.mark.unit
    def test_parse_empty_string(self):
        """Should return 0 for empty string."""
        assert parse_iso8601_duration("") == 0

    @pytest.mark.unit
    def test_parse_invalid_format(self):
        """Should return 0 for malformed input."""
        assert parse_iso8601_duration("invalid") == 0

    @pytest.mark.unit
    def test_parse_invalid_format_missing_pt(self):
        """Should return 0 for duration without PT prefix."""
        assert parse_iso8601_duration("5M30S") == 0

    @pytest.mark.unit
    def test_parse_long_video_duration(self):
        """Should parse long videos (e.g., 2+ hours)."""
        # 2 hours 30 minutes 15 seconds
        assert parse_iso8601_duration("PT2H30M15S") == 9015


class TestHasShortsTextCues:
    """Tests for detecting #shorts indicators in video metadata."""

    @pytest.mark.unit
    def test_shorts_in_title_lowercase(self):
        """Should detect 'shorts' in title (lowercase)."""
        snippet = {"title": "My cool shorts video"}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_shorts_in_title_with_hash(self):
        """Should detect '#shorts' in title."""
        snippet = {"title": "Check this out #shorts"}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_shorts_in_title_uppercase(self):
        """Should detect 'SHORTS' in title (case insensitive)."""
        snippet = {"title": "AWESOME SHORTS COMPILATION"}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_shorts_in_title_mixed_case(self):
        """Should detect 'ShOrTs' in title (mixed case)."""
        snippet = {"title": "My ShOrTs Video"}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_short_singular_in_title(self):
        """Should detect singular 'short' as well."""
        snippet = {"title": "My cool #short"}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_shorts_in_description(self):
        """Should detect '#shorts' in description."""
        snippet = {"title": "Normal title", "description": "This is a #shorts video"}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_shorts_in_tags(self):
        """Should detect 'shorts' in tags array."""
        snippet = {
            "title": "Normal title",
            "description": "Normal desc",
            "tags": ["funny", "shorts", "comedy"],
        }
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_shorts_in_tags_uppercase(self):
        """Should detect 'SHORTS' in tags (case insensitive)."""
        snippet = {"title": "Normal title", "tags": ["funny", "SHORTS"]}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_no_shorts_cues(self):
        """Should return False when no shorts indicators present."""
        snippet = {
            "title": "Regular video",
            "description": "Long form content about programming",
            "tags": ["tutorial", "coding"],
        }
        assert _has_shorts_text_cues(snippet) is False

    @pytest.mark.unit
    def test_word_boundary_shortstack(self):
        """Should not match 'shorts' within other words like 'shortstack'."""
        snippet = {"title": "Making shortstack pancakes"}
        # Regex uses word boundary: (?<!\w)#?shorts?\b
        assert _has_shorts_text_cues(snippet) is False

    @pytest.mark.unit
    def test_word_boundary_shortage(self):
        """Should not match 'shorts' in 'shortage'."""
        snippet = {"title": "Food shortage crisis"}
        assert _has_shorts_text_cues(snippet) is False

    @pytest.mark.unit
    def test_none_title(self):
        """Should handle None title gracefully."""
        snippet = {"title": None, "description": "Description here"}
        assert _has_shorts_text_cues(snippet) is False

    @pytest.mark.unit
    def test_none_description(self):
        """Should handle None description gracefully."""
        snippet = {"title": "Title here", "description": None}
        assert _has_shorts_text_cues(snippet) is False

    @pytest.mark.unit
    def test_none_tags(self):
        """Should handle None tags gracefully."""
        snippet = {"title": "Title here", "description": "Desc", "tags": None}
        assert _has_shorts_text_cues(snippet) is False

    @pytest.mark.unit
    def test_empty_tags_array(self):
        """Should handle empty tags array."""
        snippet = {"title": "Title here", "tags": []}
        assert _has_shorts_text_cues(snippet) is False

    @pytest.mark.unit
    def test_tags_with_none_values(self):
        """Should handle tags array with None values."""
        snippet = {"title": "Title", "tags": ["valid", None, "shorts"]}
        assert _has_shorts_text_cues(snippet) is True

    @pytest.mark.unit
    def test_hash_short_at_end_of_title(self):
        """Should detect #short at the end of title."""
        snippet = {"title": "Amazing video #short"}
        assert _has_shorts_text_cues(snippet) is True


class TestClassifyIsShort:
    """Tests for YouTube Shorts classification heuristic."""

    @pytest.mark.unit
    def test_long_video_always_not_short(self):
        """Videos over SHORTS_MAX_SECONDS (60 from config, fallback 180) are never Shorts."""
        snippet = {"title": "Test"}
        assert _classify_is_short(duration_seconds=61, snippet=snippet) is False

    @pytest.mark.unit
    def test_very_long_video_not_short(self):
        """Very long videos (10+ minutes) are never Shorts."""
        snippet = {"title": "Test"}
        assert _classify_is_short(duration_seconds=600, snippet=snippet) is False

    @pytest.mark.unit
    def test_short_duration_with_shorts_tag(self):
        """Short duration + #shorts tag = definitively a Short."""
        snippet = {"title": "Test #shorts"}
        assert _classify_is_short(duration_seconds=45, snippet=snippet) is True

    @pytest.mark.unit
    def test_short_duration_with_shorts_in_description(self):
        """Short duration + #shorts in description = Short."""
        snippet = {"title": "Test", "description": "Check out this #shorts"}
        assert _classify_is_short(duration_seconds=30, snippet=snippet) is True

    @pytest.mark.unit
    def test_short_duration_no_cues_defaults_to_true(self):
        """
        Ambiguous case: short duration, no cues.
        Should use SHORTS_DEFAULT_TO_SHORT (True).
        """
        snippet = {"title": "Test"}
        assert _classify_is_short(duration_seconds=45, snippet=snippet) is True

    @pytest.mark.unit
    def test_boundary_case_exactly_max_seconds(self):
        """Video at exactly SHORTS_MAX_SECONDS (60s from config)."""
        snippet = {"title": "Test"}
        # ≤ 60 is ambiguous without cues, defaults to True
        assert _classify_is_short(duration_seconds=60, snippet=snippet) is True

    @pytest.mark.unit
    def test_boundary_case_just_over_max(self):
        """Video just over SHORTS_MAX_SECONDS is not a Short."""
        snippet = {"title": "Test #shorts"}
        # Even with #shorts tag, duration > 60 = not a Short
        assert _classify_is_short(duration_seconds=61, snippet=snippet) is False

    @pytest.mark.unit
    def test_zero_duration_defaults_to_short(self):
        """Handle zero duration (unusual case)."""
        snippet = {"title": "Test"}
        # 0 ≤ 180 and no cues, defaults to True
        assert _classify_is_short(duration_seconds=0, snippet=snippet) is True

    @pytest.mark.unit
    def test_one_second_video(self):
        """Very short video (1 second)."""
        snippet = {"title": "Test"}
        assert _classify_is_short(duration_seconds=1, snippet=snippet) is True

    @pytest.mark.unit
    def test_typical_short_60_seconds(self):
        """Typical Short duration (60 seconds) with cue."""
        snippet = {"title": "Quick tip #shorts"}
        assert _classify_is_short(duration_seconds=60, snippet=snippet) is True

    @pytest.mark.unit
    def test_typical_short_without_cue(self):
        """60 second video without #shorts tag still classified as Short."""
        snippet = {"title": "Quick tip"}
        # Defaults to True when ambiguous
        assert _classify_is_short(duration_seconds=60, snippet=snippet) is True

    @pytest.mark.unit
    def test_long_video_with_shorts_tag_not_short(self):
        """Long video (>60s) with #shorts tag is still not a Short."""
        snippet = {"title": "Long tutorial #shorts"}
        # Duration overrides tag
        assert _classify_is_short(duration_seconds=300, snippet=snippet) is False

    @pytest.mark.unit
    def test_none_duration_treated_as_zero(self):
        """None duration should be treated as 0."""
        snippet = {"title": "Test"}
        # None gets converted to 0 in the function
        assert _classify_is_short(duration_seconds=None, snippet=snippet) is True


class TestGetBestThumbnailUrl:
    """Tests for thumbnail URL selection with quality fallback."""

    @pytest.mark.unit
    def test_prefers_high_quality(self):
        """Should return 'high' quality when available."""
        thumbnails = {
            "default": {"url": "https://example.com/default.jpg"},
            "medium": {"url": "https://example.com/medium.jpg"},
            "high": {"url": "https://example.com/high.jpg"},
        }
        assert _get_best_thumbnail_url(thumbnails) == "https://example.com/high.jpg"

    @pytest.mark.unit
    def test_high_quality_only(self):
        """Should return 'high' when it's the only quality."""
        thumbnails = {
            "high": {"url": "https://example.com/high.jpg"},
        }
        assert _get_best_thumbnail_url(thumbnails) == "https://example.com/high.jpg"

    @pytest.mark.unit
    def test_fallback_to_medium(self):
        """Should fallback to 'medium' when 'high' unavailable."""
        thumbnails = {
            "default": {"url": "https://example.com/default.jpg"},
            "medium": {"url": "https://example.com/medium.jpg"},
        }
        assert _get_best_thumbnail_url(thumbnails) == "https://example.com/medium.jpg"

    @pytest.mark.unit
    def test_medium_quality_only(self):
        """Should return 'medium' when it's the only quality."""
        thumbnails = {
            "medium": {"url": "https://example.com/medium.jpg"},
        }
        assert _get_best_thumbnail_url(thumbnails) == "https://example.com/medium.jpg"

    @pytest.mark.unit
    def test_fallback_to_default(self):
        """Should fallback to 'default' when others unavailable."""
        thumbnails = {
            "default": {"url": "https://example.com/default.jpg"},
        }
        assert _get_best_thumbnail_url(thumbnails) == "https://example.com/default.jpg"

    @pytest.mark.unit
    def test_empty_thumbnails_returns_none(self):
        """Should return None for empty dict."""
        assert _get_best_thumbnail_url({}) is None

    @pytest.mark.unit
    def test_unknown_quality_levels_returns_none(self):
        """Should return None when only unknown quality levels present."""
        thumbnails = {
            "ultra": {"url": "https://example.com/ultra.jpg"},
            "custom": {"url": "https://example.com/custom.jpg"},
        }
        assert _get_best_thumbnail_url(thumbnails) is None

    @pytest.mark.unit
    def test_priority_order_with_all_qualities(self):
        """Should always choose 'high' over others when all present."""
        thumbnails = {
            "default": {"url": "https://example.com/default.jpg"},
            "medium": {"url": "https://example.com/medium.jpg"},
            "high": {"url": "https://example.com/high.jpg"},
            "maxres": {"url": "https://example.com/maxres.jpg"},  # Not in priority list
        }
        # Should pick 'high', not 'maxres' (which isn't in the function's priority list)
        assert _get_best_thumbnail_url(thumbnails) == "https://example.com/high.jpg"
