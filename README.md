# Story IP Creator Agent with Twitter Integration

A LangGraph-based agent for creating, minting, registering IP assets with Story Protocol, and automatically posting about them on Twitter.

## Overview

This agent helps users create AI-generated images, upload them to IPFS, register them as IP assets on the Story blockchain, and share them on Twitter. The complete process includes:

1. Generating an image using DALL-E 3
2. Getting user approval for the generated image
3. Uploading the approved image to IPFS
4. Creating IP metadata for the IP asset
5. Negotiating licensing terms with the user
6. Minting and registering the IP on Story
7. Minting license tokens for the IP
8. Posting about the minted IP asset on Twitter with links to view it on blockchain explorers

![image](https://github.com/user-attachments/assets/31ffda62-2521-4b4d-90f8-5db1cc3f02ea)

## 🔄 Improvements from Original Repository

### 1. Twitter Integration
- Added automatic Twitter posting after successful IP minting
- Implemented `twitter_client.py` for handling Twitter API interactions
- Added comprehensive error handling for Twitter posting
- Tweets include links to Story Protocol Explorer and StoryScan for easy asset verification

### 2. Enhanced Workflow
- Streamlined the agent workflow to include Twitter posting as the final step
- Added proper error handling and user feedback throughout the process
- Improved system messages to guide users through the complete process

### 3. Documentation
- Added detailed documentation for Twitter integration in `README_TWITTER.md`
- Updated main README to include Twitter functionality
- Added tweet format examples and troubleshooting guidance

## Requirements

- Python 3.9+
- LangGraph
- LangChain
- OpenAI API key (for DALL-E and GPT models)
- Story SDK
- Twitter API credentials

## Directory Structure

The agent expects a specific directory structure to function properly:

```
your-root-directory/
├── langgraph-mcp-agent/    # This repository
│   ├── agent.py
│   ├── twitter_client.py
│   └── ...
├── story-sdk-mcp/          # The MCP server repository
│   ├── server.py
│   └── ...
├── agent-twitter-client/   # Twitter client library
│   ├── dist/
│   └── ...
```

## Installation

1. Install uv (Universal Versioner for Python):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone this repository and navigate to the project directory

3. Install dependencies using uv:

   ```bash
   uv sync
   ```

4. Set up environment variables:

   ```bash
   cp .env.example .env
   ```

   Then edit the `.env` file with your API keys and configuration, including Twitter credentials:

   ```
   # Twitter API credentials
   TWITTER_USERNAME=your_twitter_username
   TWITTER_PASSWORD=your_twitter_password
   TWITTER_EMAIL=your_twitter_email
   TWITTER_API_KEY=your_twitter_api_key
   TWITTER_API_SECRET=your_twitter_api_secret
   TWITTER_ACCESS_TOKEN=your_twitter_access_token
   TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
   ```

5. Clone the [story-sdk-mcp](https://github.com/piplabs/story-sdk-mcp) repository **into the same folder that you cloned this repository**, as shown in the above **Directory Structure** section. Follow the [README instructions](https://github.com/piplabs/story-sdk-mcp/blob/main/README.md#setup) to set up and install that mcp server, making sure to set up **all** of the .env variables. You do not have to run it, it just has to be in the same folder so this agent can access it.

6. Set up the Twitter client library in a sibling directory to this repository.

## Usage

Run the agent:

```bash
uv run agent.py
```

The agent will guide you through an interactive process to:

1. Enter an image description (e.g., "an anime style image of a person snowboarding")
2. Review the generated image and approve or request a new one
3. Set licensing terms including:
   - Commercial Revenue Share percentage (0-100%)
   - Whether to allow derivative works (yes/no)
4. Complete the minting process on the Story blockchain
5. Post about the newly minted IP asset on Twitter

### Example Workflow

When you run `agent.py`, you'll experience a workflow like this:

```
=== Story IP Creator ===
This tool will help you create and mint an image as an IP asset in the Story ecosystem.

What image would you like to create? (e.g., 'an anime style image of a person snowboarding'): blob skateboarding on a mountaintop

Starting the creation process...

[Image is generated and a link is given]

Do you like this image? (yes/no + feedback): yes
Uploading image to IPFS...

[Metadata is generated]
[Licensing terms are negotiated]
[IP is minted and registered on Story]
[License tokens are minted]

Posting to Twitter about the minted IP asset...
✅ Successfully posted to Twitter about the minted IP asset (ID: 0x25063c86986747A46DF5966Fb7753fdde49C04dA).
```

## Twitter Integration Details

For detailed information about the Twitter integration, please see [README_TWITTER.md](README_TWITTER.md).

## License

MIT
