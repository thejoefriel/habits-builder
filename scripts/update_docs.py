#!/usr/bin/env python3
"""
Generate documentation updates when a PR is merged.

Reads the PR diff and optionally any changed feature specs,
then uses Claude to generate appropriate updates to core docs.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from anthropic import Anthropic

# Core docs that should be updated when PRs are merged
CORE_DOCS = [
    "README.md",
    "docs/product-playbook.md",
    "docs/technical-design.md",
    "docs/user-flows.md",
    "docs/common-components.md",
    "docs/CHANGELOG.md",
]

SYSTEM_PROMPT = """You are a technical documentation specialist. Your job is to \
update project documentation when code changes are merged.

You will be given:
1. A PR diff showing what code/files changed
2. The PR title and description for context
3. Optionally, feature specifications that were part of the change
4. The current content of the project's core documentation files

Your task is to generate UPDATED versions of each documentation file that \
reflect the merged changes.

Guidelines:
- Maintain the existing structure and style of each document
- Add new sections or entries where appropriate
- Update existing sections if they need to reflect the changes
- Keep changes minimal and focused — only add what's necessary
- Use the same terminology and tone as the existing docs
- If a document doesn't need changes, return it UNCHANGED (you must still \
include it in the output)
- Do not remove existing content unless it's directly contradicted

CHANGELOG special handling:
- For docs/CHANGELOG.md, ADD a new entry under ## [Unreleased]
- Format: "- {brief description of what changed}"
- Only add entries for user-facing or architecturally significant changes
- Do NOT add CHANGELOG entries for documentation-only changes
- Do NOT rewrite or remove existing CHANGELOG entries

Return your response as a JSON object where each key is a file path and each \
value is the full updated content of that file:
{
  "README.md": "full updated content...",
  "docs/product-playbook.md": "full updated content...",
  "docs/technical-design.md": "full updated content...",
  "docs/user-flows.md": "full updated content...",
  "docs/common-components.md": "full updated content...",
  "docs/CHANGELOG.md": "full updated content..."
}

Return ONLY the JSON object, no other text."""

MAX_DIFF_CHARS = 50000


def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path, "r") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)


def get_current_docs() -> dict[str, str]:
    """Read all current core documentation."""
    docs = {}
    for doc_path in CORE_DOCS:
        if os.path.exists(doc_path):
            docs[doc_path] = read_file(doc_path)
    return docs


def generate_updates(
    diff_content: str,
    pr_title: str,
    pr_body: str,
    feature_specs: str | None,
    current_docs: dict[str, str],
) -> dict[str, str]:
    """Use Claude to generate documentation updates."""
    client = Anthropic()

    user_prompt = f"""# PR Title
{pr_title}

# PR Description
{pr_body or '(no description)'}

# PR Diff
```diff
{diff_content[:MAX_DIFF_CHARS]}
```
"""
    if feature_specs:
        user_prompt += f"""
# Feature Specifications Changed
{feature_specs}
"""

    user_prompt += "\n# Current Documentation\n\n"
    for path, content in current_docs.items():
        user_prompt += f"## {path}\n\n```markdown\n{content}\n```\n\n"

    user_prompt += (
        "Please generate updated versions of each documentation file. "
        "Return as JSON."
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = response.content[0].text

    # Handle potential markdown code blocks in response
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    return json.loads(response_text)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Update docs based on merged PR"
    )
    parser.add_argument(
        "--diff-file",
        required=True,
        help="Path to file containing PR diff",
    )
    parser.add_argument("--pr-title", default="", help="PR title")
    parser.add_argument(
        "--feature-files",
        nargs="*",
        help="Optional feature spec file paths",
    )
    args = parser.parse_args()

    # PR body comes from env var to avoid shell escaping issues
    pr_body = os.environ.get("PR_BODY", "")

    # Read diff
    diff_content = read_file(args.diff_file)
    if not diff_content.strip():
        print("Empty diff, nothing to do.")
        sys.exit(0)

    # Read optional feature specs
    feature_specs = None
    if args.feature_files:
        specs = []
        for f in args.feature_files:
            if os.path.exists(f):
                specs.append(f"## Feature: {Path(f).name}\n\n{read_file(f)}")
        if specs:
            feature_specs = "\n\n---\n\n".join(specs)

    current_docs = get_current_docs()

    print(f"Processing PR: {args.pr_title}")
    print(f"Diff size: {len(diff_content)} chars")
    if feature_specs:
        print(f"Feature specs included: {args.feature_files}")
    print("Generating documentation updates with Claude...")

    try:
        updated_docs = generate_updates(
            diff_content, args.pr_title, pr_body, feature_specs, current_docs
        )
    except Exception as e:
        print(f"Error generating updates: {e}")
        sys.exit(1)

    changes_made = 0
    for doc_path, content in updated_docs.items():
        if doc_path in CORE_DOCS:
            existing = current_docs.get(doc_path, "")
            if content.strip() != existing.strip():
                print(f"Updating {doc_path}...")
                write_file(doc_path, content)
                changes_made += 1
            else:
                print(f"No changes needed for {doc_path}")

    print(f"Documentation updates complete! ({changes_made} files updated)")


if __name__ == "__main__":
    main()
