import json
import helper
import bedrock
import dynamodb

def lambda_handler(event, context):
    headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
    signature = headers.get('x-hub-signature-256')
    raw_body = event['body']

    secret = helper.get_ssm_param('/ai-code-reviewer/github-webhook-secret')
    if not helper.verify_signature(event['body'].encode('utf-8'), secret, signature):
        return {
            'statusCode': 401,
            'body': json.dumps({"error": "Unauthorized"})
        }

    payload = json.loads(raw_body)
    event_type = headers.get('x-github-event')

    print(f"Received {event_type}, action: {payload.get('action')}")
    print(event_type, payload['action'])

    if event_type == 'pull_request' and payload.get('action') in ['opened', 'synchronize', 'reopened']:
        pr_number = payload['pull_request']['number']
        repo_name = payload['repository']['full_name']
        pull_request_author = payload['pull_request']['user']['login']
        print(f"Processing PR #{pr_number} from {repo_name}")
        owner, repo = repo_name.split('/')
        
        github_token = helper.get_ssm_param('/ai-code-reviewer/github-token')
        diff = helper.get_pr_diff(owner, repo, pr_number, github_token)

        filtered_diff = bedrock.filter_diff(diff)
        if not filtered_diff.strip():
            print("Skipping review generation as no relevant changes found")
            return {
                'statusCode': 200,
                'body': json.dumps({"message": "No relevant changes found"})
            }
        filtered_diff = bedrock.annotate_diff_with_line_numbers(filtered_diff)
        
        comments, model, token_usage = bedrock.review_diff(filtered_diff)
        print(f"Got {len(comments)} comments")

        dynamodb.log_review(repo, pr_number, pull_request_author, comments, model, token_usage)
        sha_id = helper.get_current_head_sha(owner, repo, pr_number, github_token)
        print(f"SHA ID: {sha_id}")
        if comments:
            print(helper.post_review_comments(owner, repo, pr_number, sha_id, github_token, comments))
        else:
            print("No issues found, skipping posting comments")


    return {
        'statusCode': 200,
        'body': json.dumps({"message": "Webhook received"})
    }