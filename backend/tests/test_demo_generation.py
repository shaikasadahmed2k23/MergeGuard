import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import demo


def test_slugify_turns_prompt_into_safe_branch_name():
    slug = demo.slugify("Add a function to validate Indian phone numbers")

    assert slug == "add-a-function-to-validate-indian-phone-numbers"
