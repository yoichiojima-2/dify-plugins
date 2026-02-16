import json
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import dashboard_template as dt

FORBIDDEN_TAGS = ["<style", "<script", "<html", "<body", "<head", "<meta", "<link", "<iframe"]
EXPECTED_TEMPLATE_TYPES = ["daily_dashboard", "weekly_dashboard", "comparison_dashboard", "shift_table", "inventory_dashboard", "demand_forecast"]


class TestDashboardTemplate(unittest.TestCase):
    def setUp(self) -> None:
        dt._TEMPLATES_CACHE = None

    def test_templates_load_successfully(self) -> None:
        data = dt._load_templates()
        self.assertIn("templates", data)
        self.assertIn("constraints", data)

    def test_all_expected_template_types_exist(self) -> None:
        data = dt._load_templates()
        templates = data["templates"]
        for ttype in EXPECTED_TEMPLATE_TYPES:
            self.assertIn(ttype, templates, f"Missing template type: {ttype}")

    def test_each_template_has_required_keys(self) -> None:
        data = dt._load_templates()
        for ttype, tinfo in data["templates"].items():
            self.assertIn("html_template", tinfo, f"{ttype}: missing html_template")
            self.assertIn("placeholders", tinfo, f"{ttype}: missing placeholders")
            self.assertIn("instructions", tinfo, f"{ttype}: missing instructions")

    def test_html_has_no_forbidden_tags(self) -> None:
        data = dt._load_templates()
        for ttype, tinfo in data["templates"].items():
            html = tinfo["html_template"]
            for tag in FORBIDDEN_TAGS:
                self.assertNotIn(
                    tag.lower(),
                    html.lower(),
                    f"{ttype}: forbidden tag {tag} found in html_template",
                )

    def test_html_has_no_empty_lines(self) -> None:
        data = dt._load_templates()
        for ttype, tinfo in data["templates"].items():
            html = tinfo["html_template"]
            self.assertNotIn(
                "\n\n",
                html,
                f"{ttype}: empty lines found in html_template (will break Dify rendering)",
            )

    def test_html_has_no_class_attributes(self) -> None:
        data = dt._load_templates()
        for ttype, tinfo in data["templates"].items():
            html = tinfo["html_template"]
            # Match class="..." or className="..." but not class inside words
            matches = re.findall(r'\bclass\s*=', html, re.IGNORECASE)
            self.assertEqual(
                len(matches),
                0,
                f"{ttype}: class= attribute found in html_template (use style= instead)",
            )

    def test_html_has_no_p_tags(self) -> None:
        data = dt._load_templates()
        for ttype, tinfo in data["templates"].items():
            html = tinfo["html_template"]
            matches = re.findall(r'<p[\s>]', html, re.IGNORECASE)
            self.assertEqual(
                len(matches),
                0,
                f"{ttype}: <p> tag found in html_template (use <div> instead)",
            )

    def test_invoke_returns_template_for_valid_type(self) -> None:
        tool = object.__new__(dt.DashboardTemplateTool)
        tool.create_json_message = lambda payload: payload

        for ttype in EXPECTED_TEMPLATE_TYPES:
            messages = list(tool._invoke({"template_type": ttype}))
            self.assertEqual(len(messages), 1)
            payload = messages[0]
            self.assertEqual(payload["template_type"], ttype)
            self.assertIn("html_template", payload)
            self.assertIn("placeholders", payload)
            self.assertIn("instructions", payload)
            self.assertIn("constraints", payload)

    def test_invoke_returns_error_for_unknown_type(self) -> None:
        tool = object.__new__(dt.DashboardTemplateTool)
        tool.create_json_message = lambda payload: payload

        messages = list(tool._invoke({"template_type": "nonexistent"}))
        self.assertEqual(len(messages), 1)
        payload = messages[0]
        self.assertIn("error", payload)
        self.assertIn("available_types", payload)
        self.assertEqual(sorted(payload["available_types"]), sorted(EXPECTED_TEMPLATE_TYPES))

    def test_invoke_returns_error_for_empty_type(self) -> None:
        tool = object.__new__(dt.DashboardTemplateTool)
        tool.create_json_message = lambda payload: payload

        messages = list(tool._invoke({"template_type": ""}))
        self.assertEqual(len(messages), 1)
        payload = messages[0]
        self.assertIn("error", payload)
        self.assertIn("available_types", payload)

    def test_constraints_has_rules(self) -> None:
        data = dt._load_templates()
        constraints = data["constraints"]
        self.assertIn("forbidden_tags", constraints)
        self.assertIn("rules", constraints)
        self.assertGreater(len(constraints["rules"]), 0)

    def test_instructions_exemplars_have_no_forbidden_tags(self) -> None:
        """Exemplar HTML snippets in instructions should also comply with Dify constraints."""
        data = dt._load_templates()
        for ttype, tinfo in data["templates"].items():
            for key, value in tinfo["instructions"].items():
                if "exemplar" in key:
                    for tag in FORBIDDEN_TAGS:
                        self.assertNotIn(
                            tag.lower(),
                            value.lower(),
                            f"{ttype}.instructions.{key}: forbidden tag {tag}",
                        )

    def test_json_file_is_valid(self) -> None:
        """Ensure the JSON file can be parsed without errors."""
        raw = dt._TEMPLATES_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertIsInstance(data, dict)


if __name__ == "__main__":
    unittest.main()
