#!/usr/bin/env python3
"""
Generate documentation updates when a new feature spec is merged.

This script:
1. Reads the new feature spec(s)
2. Reads the existing core documentation
3. Uses Claude to generate appropriate updates
4. Outputs the updated docs (the GitHub Action handles creating the PR)
"""

import os
import sys
import json
from pathlib import Path
from anthropic import Anthropic

# Core docs that should be updated when features are merged
CORE_DOCS = [
    "docs/ai/PROJECT_OVERVIEW.md",
    "docs/ai/ARCHITECTURE.md",
    "docs/ai/PRODUCT_PLAYBOOK.md",
    "docs/ai/USER_JOURNEYS.md",
]

SYSTEM_PROMPT = """You are a technical documentation specialist. Your job is to update project documentation when new features are added.

You will be given:
1. A new feature specification
2. The current content of several core documentation files

Your task is to generate UPDATED versions of each documentation file that incorporate the new feature.

Guidelines:
- Maintain the existing structure and style of each document
- Add new sections or entries where appropriate
- Update existing sections if they need to reflect the new feature
- Keep changes minimal and focused - only add what's necessary
- Use the same terminology and tone as the existing docs
- If a document doesn't need changes for this feature, return it unchanged
- Do not remove existing content unless it's directly contradicted by the new feature

Return your response as a JSON object with this structure:
{
  "docs/ai/PROJECT_OVERVIEW.md": "full updated content...",
  "docs/ai/ARCHITECTURE.md": "full updated content...",
  "docs/ai/PRODUCT_PLAYBOOK.md": "full updated content...",
  "docs/ai/USER_JOURNEYS.md": "full updated content..."
}

Return ONLY the JSON object, no other text."""


def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path, "r") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)


def get_feature_specs(feature_files: list[str]) -> str:
    """Read and concatenate all feature specs."""
    specs = []
    for file_path in feature_files:
        content = read_file(file_path)
        specs.append(f"## Feature: {Path(file_path).name}\n\n{content}")
    return "\n\n---\n\n".join(specs)


def get_current_docs() -> dict[str, str]:
    """Read all current core documentation."""
    docs = {}
    for doc_path in CORE_DOCS:
        if os.path.exists(doc_path):
            docs[doc_path] = read_file(doc_path)
    return docs


def generate_updates(feature_specs: str, current_docs: dict[str, str]) -> dict[str, str]:
    """Use Claude to generate documentation updates."""
    client = Anthropic()

    # Build the user prompt
    user_prompt = f"""# New Feature Specification(s)

{feature_specs}

---

# Current Documentation

"""
    for path, content in current_docs.items():
        user_prompt += f"## {path}\n\n```markdown\n{content}\n```\n\n"

    user_prompt += """---

Please generate updated versions of each documentation file that incorporate the new feature(s). Return as JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    # Parse the JSON response
    response_text = response.content[0].text

    # Handle potential markdown code blocks in response
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    return json.loads(response_text)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python update_docs_from_feature.py <feature_file1> [feature_file2] ...")
        sys.exit(1)

    feature_files = sys.argv[1:]

    # Validate feature files exist
    for f in feature_files:
        if not os.path.exists(f):
            print(f"Error: Feature file not found: {f}")
            sys.exit(1)

    print(f"Processing {len(feature_files)} feature spec(s)...")

    # Read inputs
    feature_specs = get_feature_specs(feature_files)
    current_docs = get_current_docs()

    print("Generating documentation updates with Claude...")

    # Generate updates
    try:
        updated_docs = generate_updates(feature_specs, current_docs)
    except Exception as e:
        print(f"Error generating updates: {e}")
        sys.exit(1)

    # Write updated docs
    for doc_path, content in updated_docs.items():
        if doc_path in CORE_DOCS:
            print(f"Updating {doc_path}...")
            write_file(doc_path, content)

    print("Documentation updates complete!")


if __name__ == "__main__":
    main()
