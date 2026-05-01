import json
import os
import sys
import urllib.error
import urllib.request


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
REVIEW_MARKER = "<!-- llm-issue-review -->"


def require_env(name):
    value = os.environ.get(name)
    if not value:
        if name == "OPENAI_API_KEY":
            repo = os.environ.get("GITHUB_REPOSITORY", "this repository")
            raise RuntimeError(
                "Missing OPENAI_API_KEY. Add it as a repository secret at "
                f"https://github.com/{repo}/settings/secrets/actions."
            )
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def request_json(method, url, token=None, payload=None, headers=None):
    body = None
    request_headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "issue-llm-review-action",
    }
    if headers:
        request_headers.update(headers)
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {error.code} {detail}") from error


def github_api(method, path, payload=None):
    repo = require_env("GITHUB_REPOSITORY")
    token = require_env("GITHUB_TOKEN")
    return request_json(method, f"https://api.github.com/repos/{repo}{path}", token=token, payload=payload)


def load_event():
    event_path = require_env("GITHUB_EVENT_PATH")
    with open(event_path, "r", encoding="utf-8") as file:
        return json.load(file)


def ensure_target_repository():
    target_repository = os.environ.get("TARGET_REPOSITORY", "").strip()
    current_repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if target_repository and current_repository != target_repository:
        raise RuntimeError(
            f"This workflow is configured for {target_repository}, "
            f"but it is running in {current_repository}."
        )


def get_issue(event):
    manual_issue_number = os.environ.get("MANUAL_ISSUE_NUMBER")
    if manual_issue_number:
        return github_api("GET", f"/issues/{manual_issue_number}")

    issue = event.get("issue")
    if not issue:
        raise RuntimeError("This workflow must be triggered by an issue event or workflow_dispatch input.")
    return issue


def has_trigger_label(issue):
    trigger_label = os.environ.get("REVIEW_TRIGGER_LABEL", "").strip()
    if not trigger_label:
        return True

    labels = issue.get("labels", [])
    label_names = {label.get("name", "") for label in labels}
    return trigger_label in label_names


def build_prompt(issue):
    language = os.environ.get("REVIEW_LANGUAGE", "ko")
    title = issue.get("title") or ""
    body = issue.get("body") or ""
    labels = ", ".join(label.get("name", "") for label in issue.get("labels", [])) or "(none)"

    return f"""
You are reviewing a GitHub issue before implementation.
Write the review in {language}.

Focus on:
- Whether the requirement is clear and actionable
- Missing context or acceptance criteria
- Implementation risks and edge cases
- Questions to ask before starting
- A concise improved issue description if the original is ambiguous

Keep the review practical, respectful, and concise.

Issue title:
{title}

Issue labels:
{labels}

Issue body:
{body}
""".strip()


def call_openai(prompt):
    api_key = require_env("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    payload = {
        "model": model,
        "instructions": "You are a senior software engineer helping triage GitHub issues.",
        "input": prompt,
    }
    response = request_json(
        "POST",
        OPENAI_RESPONSES_URL,
        token=None,
        payload=payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    output_text = response.get("output_text")
    if output_text:
        return output_text.strip()

    chunks = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    if not chunks:
        raise RuntimeError("OpenAI response did not contain output text.")
    return "\n".join(chunks).strip()


def find_existing_review_comment(issue_number):
    comments = github_api("GET", f"/issues/{issue_number}/comments?per_page=100")
    for comment in comments:
        if REVIEW_MARKER in (comment.get("body") or ""):
            return comment
    return None


def upsert_review_comment(issue_number, review):
    body = f"{REVIEW_MARKER}\n## LLM Issue Review\n\n{review}"
    existing = find_existing_review_comment(issue_number)
    if existing:
        github_api("PATCH", f"/issues/comments/{existing['id']}", {"body": body})
        print(f"Updated existing LLM review comment on issue #{issue_number}.")
    else:
        github_api("POST", f"/issues/{issue_number}/comments", {"body": body})
        print(f"Created LLM review comment on issue #{issue_number}.")


def main():
    ensure_target_repository()
    event = load_event()
    issue = get_issue(event)
    issue_number = issue["number"]

    if issue.get("pull_request"):
        print(f"Skipping #{issue_number}: this issue is a pull request.")
        return

    if not has_trigger_label(issue):
        print(f"Skipping #{issue_number}: REVIEW_TRIGGER_LABEL is set and not present.")
        return

    prompt = build_prompt(issue)
    review = call_openai(prompt)
    upsert_review_comment(issue_number, review)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
