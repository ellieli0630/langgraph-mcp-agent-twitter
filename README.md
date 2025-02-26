# IP Asset Creation Agent with LangGraph

This repository contains an agent that helps users create and mint IP assets on Story Protocol using LangGraph. The agent guides users through the entire process, from content creation to minting and registering the IP asset on the blockchain.

## Features

- **Multiple Content Creation Options**:
  - Upload local image/video files
  - Generate images using OpenAI DALL-E
  - Generate videos using Luma AI (placeholder implementation)

- **Comprehensive IP Asset Workflow**:
  - Content creation and review
  - IPFS upload
  - Metadata generation
  - Terms negotiation
  - IP asset minting and registration
  - License token minting
  - Twitter integration for announcing newly minted assets

- **Twitter Integration**:
  - Automatically posts about newly minted IP assets
  - Includes asset ID, transaction hash, and links to explorers
  - See [Twitter Integration Documentation](README_TWITTER.md) for details

## Prerequisites

- Python 3.9+
- Story Protocol SDK
- OpenAI API key
- Twitter API credentials (if using Twitter integration)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/langgraph-mcp-agent.git
cd langgraph-mcp-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
```

4. Edit the `.env` file with your API keys and credentials.

## Usage

Run the agent:
```bash
python agent.py
```

The agent will guide you through the following steps:
1. Choose a content creation method:
   - Upload a local image/video file
   - Generate an image using OpenAI DALL-E
   - Generate a video using Luma AI
2. Review the generated/uploaded content
3. Create metadata for the IP asset
4. Negotiate terms for the IP asset
5. Mint and register the IP asset
6. Mint license tokens
7. Post about the minted IP asset on Twitter

## Improvements from Original Repository

This repository builds upon the original Story Protocol example by adding:
- Multiple content creation options (local upload, DALL-E, Luma)
- Enhanced human review process for generated content
- Twitter integration for announcing minted assets
- Improved error handling and user feedback
- More comprehensive documentation

## License

This project is licensed under the MIT License - see the LICENSE file for details.
