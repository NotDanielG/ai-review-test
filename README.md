# AI Code Reviewer Bot

An AI code reviewer bot that provides feedback to pull request made for a repository, meant to be an internal developer tool. When a pull request is made, it sends out a webhook event to AWS API Gateway, which triggers a Lambda function. This lambda function invokes a model from AWS Bedrock, the model Google Gemma was chosen due to it being a lightweight model. It pulls the git-diff from the pull request and it provides feedback based on a customizable style guide located in the bedrock.py file. It then post these comments onto the pull request and then logs this interaction onto AWS DynamoDB so you can look up the token cost.

## Architecture

- Github sends out a webhook event when a pull request is made in the repository
- AWS API Gateway receives event and triggers a Lambda function
- Lambda function verifies the signature header using a secret token stored in AWS System Managers (SSM) Parameter Store
- Lambda function gets the git diff from pull request, then prompts a model (Google Gemma) from AWS Bedrock with the git diff and style guide
- Once the Lambda function receives a response, it logs the results into AWS DynamoDB
- Lambda function then posts results back to the pull request on Github
  
## Tech stack
- AWS (Lambda, API Gateway, SSM, Bedrock, DynamoDB)
- Python (Code in Lambda function)

## Project Structure
- lambda_function.py   - Main file, receives webhook event and processes it
- helper.py            - Helper file, stores vital functions to help with verification, processing the git diff and post feedback to Github
- bedrock.py           - Asks the prompt to the AWS Bedrock model (can be configured), holds the style guide and instructions (which can also be configured)
- dynamodb.py          - Stores function to log the results of AI feedback. Note that each model has different response structures, requiring changes here 

## Setup

- On AWS Lambda, create a Lambda function. Copy the name
- On AWS API Gateway, create an HTTP API. Copy the provided 'Invoke URL'
  - Configure it to trigger the Lambda function
- Generate a random secret string to work as your Github secret token
- On Github, go to your repository's setting and click on Webhook
  - Paste the 'Invoke URL', then add a '/' with the Lambda name together into the Payload URL
  - Paste the random secret token to configure it to this webhook
  - Check off the pull request event button at the bottom
- On Github, create a personal access token. Copy both the token and the secret key.
- On AWS store the Github secret token and Github access token onto SSM's Parameter store.
- Create a DynamoDB table
- Configure the AWS Lambda's execution role permissions. It needs the following:
  - Allow Bedrock: InvokeModel
  - Allow SSM: GetParameter for both Github tokens (Webhook secret and access token)
  - Allow DynamoDB: PutItem, Query
- On AWS Lambda, paste the .py files and deploy
  - Make sure the names of the your DynamoDB table and SSM Parameters are reflected in the .py files (line 5 in dynamodb.py and line 11 + 31 in lambda_function.py)

## Result
Once you deploy the AWS Lambda function, go create a separate branch and make a pull request to the main branch. I used the test.py file just to test out this functionality. An example of the AI feedback should look like the following:
<img width="786" height="684" alt="image" src="https://github.com/user-attachments/assets/e3d63fc7-e10f-413f-aedf-1e0dedbb5546" />

