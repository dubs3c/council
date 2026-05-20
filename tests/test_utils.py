import unittest

from council.utils import parse_json_response


class TestJsonParsing(unittest.TestCase):
    def test_parses_valid_json_object(self):
        response = '{"action": "revise", "reasoning": "I made a mistake"}'
        expected = {"action": "revise", "reasoning": "I made a mistake"}
        self.assertEqual(parse_json_response(response), expected)

    def test_parses_json_with_whitespace(self):
        response = """

  {
    "name": "Agent",
    "role": "Tester"
  }

"""
        expected = {"name": "Agent", "role": "Tester"}
        self.assertEqual(parse_json_response(response), expected)

    def test_parses_nested_json(self):
        response = '{"list": ["item1", "item2"], "meta": {"count": 2}}'
        expected = {"list": ["item1", "item2"], "meta": {"count": 2}}
        self.assertEqual(parse_json_response(response), expected)

    def test_invalid_json_raises_value_error(self):
        response = "This is just text with no JSON structure."
        with self.assertRaises(ValueError):
            parse_json_response(response)

    def test_markdown_wrapped_json_raises_value_error(self):
        response = """
```json
{"key": "value"}
```
"""
        with self.assertRaises(ValueError):
            parse_json_response(response)


if __name__ == "__main__":
    unittest.main()
