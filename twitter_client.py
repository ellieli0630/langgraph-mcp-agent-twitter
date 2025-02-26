"""
Twitter client for posting tweets about minted IP assets.
"""

import os
import sys
import asyncio
import json
from dotenv import load_dotenv
import subprocess
import time

# Add the agent-twitter-client directory to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agent-twitter-client'))

# Load environment variables
load_dotenv()

class TwitterClient:
    """Twitter client for posting tweets."""
    
    def __init__(self):
        """Initialize the Twitter client."""
        self.username = os.getenv("TWITTER_USERNAME")
        self.password = os.getenv("TWITTER_PASSWORD")
        self.email = os.getenv("TWITTER_EMAIL")
        self.api_key = os.getenv("TWITTER_API_KEY")
        self.api_secret = os.getenv("TWITTER_API_SECRET")
        self.access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        
        # Validate environment variables
        if not all([self.username, self.password, self.email]):
            print("Warning: Twitter credentials not fully configured in .env file")
    
    async def post_tweet(self, tweet_text, image_url=None):
        """Post a tweet to Twitter using the agent-twitter-client library.
        
        Args:
            tweet_text (str): The text content of the tweet
            image_url (str, optional): URL to an image to include in the tweet
            
        Returns:
            dict: Result of the tweet operation
                - success (bool): Whether the tweet was posted successfully
                - message (str): Success or error message
        """
        try:
            # Create a temporary script to post the tweet
            temp_script_path = os.path.join(os.path.dirname(__file__), f'temp_tweet_{int(time.time())}.js')
            
            try:
                # Write the Node.js script content
                with open(temp_script_path, 'w') as f:
                    f.write("""
                    const { Scraper } = require('../agent-twitter-client/dist/node/cjs/index.cjs');
                    
                    async function postTweet() {
                        try {
                            const scraper = new Scraper();
                            
                            // Login with credentials
                            await scraper.login(
                                process.env.TWITTER_USERNAME,
                                process.env.TWITTER_PASSWORD,
                                process.env.TWITTER_EMAIL
                            );
                            
                            console.log('Logged in successfully');
                            
                            // Post the tweet
                            const tweetText = process.argv[2];
                            const imageUrl = process.argv[3] !== 'null' ? process.argv[3] : undefined;
                            
                            console.log(`Posting tweet: ${tweetText}`);
                            if (imageUrl) {
                                console.log(`With image: ${imageUrl}`);
                            }
                            
                            // Send the tweet
                            const result = await scraper.sendTweet(tweetText);
                            
                            // Return the result - note that sendTweet doesn't return tweet ID
                            // We'll just indicate success
                            console.log(JSON.stringify({
                                success: true,
                                message: "Tweet posted successfully"
                            }));
                            
                            process.exit(0);
                        } catch (error) {
                            console.error('Error posting tweet:', error.message);
                            console.log(JSON.stringify({
                                success: false,
                                error: error.message
                            }));
                            process.exit(1);
                        }
                    }
                    
                    postTweet();
                    """)
                
                # Run the Node.js script
                result = subprocess.run(
                    ["node", temp_script_path, tweet_text, str(image_url) if image_url else "null"],
                    capture_output=True,
                    text=True,
                    env=os.environ.copy()
                )
                
                # Parse the output
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    try:
                        # Try to parse as JSON
                        data = json.loads(line)
                        if 'success' in data:
                            return data
                    except json.JSONDecodeError:
                        # Not a JSON line, just a log message
                        continue
                
                # If we couldn't parse any JSON, check the return code
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Error posting tweet: {result.stderr}"
                    }
                
                return {
                    "success": True,
                    "message": "Tweet posted successfully"
                }
                    
            finally:
                # Clean up the temporary script
                try:
                    os.remove(temp_script_path)
                except:
                    pass
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Error posting tweet: {str(e)}"
            }

    async def post_ip_minted_tweet(self, ip_id, tx_hash, content_url=None, content_type="image"):
        """
        Post a tweet announcing a newly minted IP asset.
        
        Args:
            ip_id (str): The ID of the IP asset
            tx_hash (str): The transaction hash of the minting transaction
            content_url (str, optional): URL to the content to include in the tweet
            content_type (str, optional): Type of content ("image" or "video")
            
        Returns:
            dict: Result of the tweet operation
        """
        # Create the tweet text
        tweet_text = f"🎉 Just minted a new {content_type} as an IP asset on Story Protocol! 🎉\n\n"
        tweet_text += f"IP ID: {ip_id}\n"
        tweet_text += f"Transaction: {tx_hash[:8]}...{tx_hash[-6:]}\n\n"
        tweet_text += f"View on Explorer: https://aeneid.explorer.story.foundation/ipa/{ip_id}\n"
        tweet_text += f"View on StoryScan: https://aeneid.storyscan.xyz/tx/{tx_hash}\n\n"
        
        # Add appropriate hashtags based on content type
        if content_type == "video":
            tweet_text += "#StoryProtocol #Web3 #IP #Video #NFT"
        else:
            tweet_text += "#StoryProtocol #Web3 #IP #NFT"
        
        # Post the tweet
        result = await self.post_tweet(tweet_text, content_url)
        
        return result

async def post_ip_minted_tweet(ip_id, tx_hash, image_url=None):
    """
    Post a tweet announcing a newly minted IP asset.
    
    Args:
        ip_id (str): The ID of the IP asset
        tx_hash (str): The transaction hash of the minting transaction
        image_url (str, optional): URL to an image to include in the tweet
        
    Returns:
        dict: Result of the tweet operation
    """
    # Create the tweet text
    tweet_text = f"🎉 Just minted a new IP asset on Story Protocol! 🎉\n\n"
    tweet_text += f"IP ID: {ip_id}\n"
    tweet_text += f"Transaction: {tx_hash[:8]}...{tx_hash[-6:]}\n\n"
    tweet_text += f"View on Explorer: https://aeneid.explorer.story.foundation/ipa/{ip_id}\n"
    tweet_text += f"View on StoryScan: https://aeneid.storyscan.xyz/tx/{tx_hash}\n\n"
    tweet_text += "#StoryProtocol #Web3 #IP #NFT"
    
    # Create a Twitter client
    client = TwitterClient()
    
    # Post the tweet
    result = await client.post_tweet(tweet_text, image_url)
    
    return result
