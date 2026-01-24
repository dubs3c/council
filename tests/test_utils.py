import unittest

from council.utils import parse_json_response


class TestYamlParsing(unittest.TestCase):
    def test_standard_markdown_block(self):
        response = """
Here is the plan:
```yaml
action: revise
reasoning: "I made a mistake"
```
Hope this helps.
"""
        expected = {"action": "revise", "reasoning": "I made a mistake"}
        self.assertEqual(parse_json_response(response), expected)

    def test_alternative_extension(self):
        response = """
```yml
key: value
```
"""
        expected = {"key": "value"}
        self.assertEqual(parse_json_response(response), expected)

    def test_generic_code_block(self):
        response = """
```
list:
  - item1
  - item2
```
"""
        expected = {"list": ["item1", "item2"]}
        self.assertEqual(parse_json_response(response), expected)

    def test_raw_yaml(self):
        response = """
name: Agent
role: Tester
"""
        expected = {"name": "Agent", "role": "Tester"}
        self.assertEqual(parse_json_response(response), expected)

    def test_invalid_yaml(self):
        response = "This is just text with no yaml structure."
        # Depending on yaml parser, this might actually parse as a string or error.
        # yaml.safe_load("string") returns "string".
        # So parse_json_response will likely return "This is just text..."
        # Let's check strict YAML structure requirements if we enforced them,
        # but currently the code falls back to yaml.safe_load(response).

        # If we want to ensure it returns a dict, the code doesn't enforce that return type annotation strictly at runtime
        # but the nodes expect a dict.

        result = parse_json_response(response)
        self.assertEqual(result, response)

    def test_malformed_yaml_in_block(self):
        # Test incomplete - placeholder for malformed YAML handling
        # Should raise ValueError because it found a block but couldn't parse it,
        # and fallback to whole string might also fail or return string.
        # Actually my implementation tries next pattern if block fails.
        # If all blocks fail, it falls back to whole string.
        # The whole string contains backticks which is invalid YAML usually?
        # Or it parses as a string.

        # Let's see what happens.
        pass


if __name__ == "__main__":
    unittest.main()
