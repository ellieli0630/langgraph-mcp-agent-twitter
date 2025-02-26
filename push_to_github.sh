#!/bin/bash

# Script to push the langgraph-mcp-agent repository to GitHub

# Check if the user provided a GitHub username and repository name
if [ $# -ne 2 ]; then
  echo "Usage: $0 <github_username> <repository_name>"
  echo "Example: $0 yourusername langgraph-mcp-agent-twitter"
  exit 1
fi

GITHUB_USERNAME=$1
REPO_NAME=$2

echo "Setting up GitHub repository for $GITHUB_USERNAME/$REPO_NAME..."

# Add the remote repository URL
git remote add origin https://github.com/$GITHUB_USERNAME/$REPO_NAME.git

# Push the code to GitHub
echo "Pushing code to GitHub..."
git push -u origin main

# Check if the push was successful
if [ $? -eq 0 ]; then
  echo "✅ Successfully pushed to GitHub!"
  echo "Your repository is now available at: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
else
  echo "❌ Failed to push to GitHub. Please check your credentials and try again."
fi
