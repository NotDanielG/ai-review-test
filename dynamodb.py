import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb')
history_table = dynamodb.Table('code-review-history')

def log_review(repo, pr_number, pr_author, comments, model_type, token_usage):
    severity_count = {"critical": 0, "suggestion": 0, "nitpick": 0, "other": 0}
    for c in comments:
        severity_type = c.get('severity').lower()
        if severity_type not in severity_count:
            severity_type = "other"
        severity_count[severity_type] = severity_count.get(severity_type, 0) + 1
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        history_table.put_item(Item={
            'repo': repo,
            'review_id': f"{pr_number}#{timestamp}",
            'pr_number': pr_number,
            'pr_author': pr_author,
            'timestamp': timestamp,
            'total_comments': len(comments),
            'comments': comments,
            'model': model_type,
            'token_usage': {
                'input_tokens': token_usage['prompt_tokens'],
                'output_tokens': token_usage['completion_tokens'],
                'total_tokens': token_usage['total_tokens']
            },
            'severity_count': severity_count
        })
        print(f"Logged review info for repo {repo} PR#{pr_number}")
    except Exception as e:
        print(f"Failed to log review history due to error: {e}")