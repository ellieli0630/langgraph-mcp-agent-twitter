# Twitter Integration for IP Minting Agent

This document explains how to use the Twitter integration for the IP Minting Agent.

## Overview

The Twitter integration allows the agent to automatically post tweets about newly minted IP assets on the Story Protocol. This integration uses the `agent-twitter-client` library, which is a Node.js-based Twitter client that handles authentication and tweet posting.

## Requirements

- Node.js (v14 or later)
- Python 3.8+
- agent-twitter-client library (installed in a sibling directory)

## Setup

1. Make sure the `agent-twitter-client` library is built and available in a sibling directory to this project.

2. Set up the required environment variables in your `.env` file:

```
TWITTER_USERNAME=your_twitter_username
TWITTER_PASSWORD=your_twitter_password
TWITTER_EMAIL=your_twitter_email
```

## Testing

Several test scripts are provided to verify the Twitter integration:

### 1. Test Twitter Login

To test if the Twitter client can log in successfully:

```bash
python test_twitter_login_only.py
```

This script will attempt to log in to Twitter using the credentials from your `.env` file and report whether the login was successful.

### 2. Test Tweet Posting

To test if the Twitter client can post a tweet:

```bash
python test_twitter_post.py
```

This script will log in to Twitter and post a test tweet.

### 3. Test IP Minted Tweet

To test the specific functionality of posting about a newly minted IP asset:

```bash
python test_ip_minted_tweet.py
```

This script will create a sample IP minted tweet with mock data.

## Integration with the Agent

The Twitter integration is fully integrated into the agent workflow:

1. After an IP asset is minted and license tokens are created, the workflow automatically proceeds to the `PostToTwitter` node.
2. The `PostToTwitter` node extracts the IP ID, transaction hash, and image URL from previous messages.
3. It then calls the `post_ip_minted_tweet` function to post a tweet about the newly minted IP asset.
4. The tweet includes:
   - The IP ID
   - A shortened version of the transaction hash
   - Links to view the asset on the Story Protocol Explorer and StoryScan
   - Relevant hashtags
   - The image of the IP asset (if available)

## Tweet Format

The tweets posted by the agent follow this format:

```
🎉 Just minted a new IP asset on Story Protocol! 🎉

IP ID: [IP_ID]
Transaction: [TX_HASH_SHORT]

View on Explorer: https://aeneid.explorer.story.foundation/ipa/[IP_ID]
View on StoryScan: https://aeneid.storyscan.xyz/tx/[TX_HASH]

#StoryProtocol #Web3 #IP #NFT
```

## Troubleshooting

If you encounter issues with the Twitter integration:

1. **Login Issues**: Make sure your Twitter credentials in the `.env` file are correct.
2. **Node.js Issues**: Ensure Node.js is installed and accessible from the command line.
3. **Library Issues**: Check that the `agent-twitter-client` library is properly built and available in the expected location.
4. **Rate Limiting**: Twitter may rate-limit your account if you post too many tweets in a short period.

## Notes

- The Twitter client uses a temporary Node.js script for each tweet posting operation.
- The script is automatically cleaned up after execution.
- The integration handles errors gracefully and reports them back to the agent.
