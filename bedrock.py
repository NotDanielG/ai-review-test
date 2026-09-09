import boto3
import json

IGNORED_FILE_PATTERNS = [
    'package-lock.json', 'yarn.lock', '.min.js', 
    '/dist/', '/build/', '/node_modules/', '/vendor/'
]

STYLE_GUIDE = """
- Functions should have descriptive names (no single letters except loop indices)
- Avoid bare except, catch specific exceptions
- No hardcoded secrets, API keys, or credentials in code
- Functions longer than 40 lines should be considered for splitting
- Use f-strings instead of .format() or % formatting
- All public functions should have a docstring
- Avoid mutable default arguments (e.g. def f(x=[]))
"""

def review_diff(diff):
  bedrock = boto3.client('bedrock-runtime', 'us-east-1')
  prompt = f"""You are a senior software engineer conducting a code review.
Review the following git diff against the style guide below.

STYLE GUIDE:
{STYLE_GUIDE}

DIFF:
{diff}

Instructions:
- Only flag genuine issues. If the code is fine, return an empty array.
- Only comment on lines with a leading +
- DIFF (each changed/context line is prefixed with its actual [LINE N] number):
  For each issue, use the exact number shown in the [LINE N] tag for that line — 
  do not calculate or guess the line number yourself.
- Be specific and actionable — say what to change, not just what's wrong.
- Limit yourself to the most important 5 issues maximum. Prioritize correctness 
  and security issues over style nitpicks.

Return ONLY valid JSON, no other text, in this exact format. Do not add or assume a file extension, if it did not have one already:
[
  {{
    "file": "path/to/file",
    "line": 42,
    "severity": "critical",
    "comment": "specific, actionable feedback"
  }}
]

severity must be one of: "critical", "suggestion", "nitpick"
file must match what is shown in the diff — do not modify it.
"""
  response = bedrock.invoke_model(
    modelId='google.gemma-3-4b-it',
    body=json.dumps({
        "max_tokens": 512,
        "messages": [{
            "role": "user", 
            "content": prompt
        }],
        "temperature": 0.5
    })
  )
  result = json.loads(response['body'].read())
  print('Result:', result)
  raw_text, model, usage = result['choices'][0]['message']['content'], result['model'], result['usage']

  cleaned = raw_text.strip().removeprefix('```json').removesuffix('```').strip()
  try:
    comments = json.loads(cleaned)
    return comments, model, usage
  except json.JSONDecodeError as e:
    print(f"Failed to parse Bedrock response: {e}")
    print(f"Raw response: {raw_text}")
    raise
  

def filter_diff(diff):
  files = diff.split('diff --git ')
  kept = []
  for f in files:
    if not f.strip() and any(pattern in f for pattern in IGNORED_FILE_PATTERNS):
      continue
    kept.append('diff --git ' + f)
  return '\n'.join(kept)

import re

def annotate_diff_with_line_numbers(diff_text):
  annotated_lines = []
  current_line = None

  for line in diff_text.split('\n'):
    hunk_match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
    if hunk_match:
      current_line = int(hunk_match.group(1))
      annotated_lines.append(line)
      continue

    if line.startswith('+') and not line.startswith('+++'):
      annotated_lines.append(f"[LINE {current_line}] {line}")
      current_line += 1
    elif line.startswith('-') and not line.startswith('---'):
      annotated_lines.append(line)  # removed lines don't consume a new-file line number
    elif not line.startswith('diff --git') and not line.startswith('index') \
        and not line.startswith('new file mode') and not line.startswith('---') \
        and not line.startswith('+++'):
      if current_line is not None:
          annotated_lines.append(f"[LINE {current_line}] {line}")
          current_line += 1
      else:
        annotated_lines.append(line)
    else:
      annotated_lines.append(line)

  return '\n'.join(annotated_lines)