import boto3
import hmac
import hashlib
import urllib
import json

ssm = boto3.client('ssm')

def get_current_head_sha(owner, repo, pr_number, github_token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {github_token}')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    req.add_header('User-Agent', 'ai-code-reviewer')

    try:
        with urllib.request.urlopen(req) as response:
            pr_data = json.loads(response.read().decode('utf-8'))
            return pr_data['head']['sha']
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        raise

def get_ssm_param(name, decrypt=True):
    response = ssm.get_parameter(Name=name, WithDecryption=decrypt)
    return response['Parameter']['Value']

def verify_signature(payload_body, secret_token, signature_header):
    if not signature_header:
        return False

    expected_signature = 'sha256=' + hmac.new(
        secret_token.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)

def get_pr_diff(owner, repo, pr_number, github_token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {github_token}')
    req.add_header('Accept', 'application/vnd.github.v3.diff')
    req.add_header('User-Agent', 'ai-code-reviewer')

    try:
        with urllib.request.urlopen(req) as response:
            pr_data = response.read().decode('utf-8')
            return pr_data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        raise

def post_review_comments(owner, repo, pr_number, sha_id, github_token, comments):
    review_comments = []
    for comment in comments:
        comment_obj = {
            "body": f"**[{comment['severity'].upper()}]** {comment['comment']}",
            "path": comment['file'],
            "line": comment['line'],
            "side": "RIGHT",
        }
        if comment.get("start_line"):
            comment_obj["start_line"] = comment["start_line"]
            comment_obj["start_side"] = "RIGHT"
        review_comments.append(comment_obj)
    print(review_comments)

    try:
        print(sha_id)
        print(f"Comments being sent: {json.dumps(comments, indent=2)}")
        failed = post_review(owner, repo, pr_number, sha_id, github_token, review_comments)
        if failed:
            print("Failed to post batch comments, trying individual posts...")
            failed = []
            for c in comments:
                single_comment = [c]
                failed.append(post_review(owner, repo, pr_number, sha_id, github_token, single_comment))
            if failed:
                post_general_comment(owner, repo, pr_number, github_token, failed)
        # print(f"Posted {len(comments)} comments in batch")
    except urllib.error.HTTPError as e:
        print(f"Failed to post individual comment: {e.code} - {e.read().decode('utf-8')}")

def post_review(owner, repo, pr_number, sha_id, github_token, comments):
    review_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    payload = {
        "commit_id": sha_id,
        "body": f"Code Review Comments - {len(comments)} issues found",
        "event": "COMMENT",
        "comments": comments
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(review_url, data=data, method='POST')
    req.add_header('Authorization', f'token {github_token}')
    req.add_header('User-Agent', 'ai-code-reviewer')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("Posting complete:", result)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {error_body}")
        return comments

def post_general_comment(owner, repo, pr_number, github_token, failed_comments):
    body = "Additional notes that could not attach to lines:\n\n"
    for c in failed_comments:
        body += f"- `{c['file']}` — **[{c['severity']}]** {c['comment']}\n"

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    data = json.dumps({"body": body}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', f'token {github_token}')
    req.add_header('User-Agent', 'ai-code-reviewer')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))