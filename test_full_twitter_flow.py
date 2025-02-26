#!/usr/bin/env python3
"""
Test script to simulate the full flow of generating an image, minting IP, and posting to Twitter
"""

import os
import sys
import asyncio
import random
from dotenv import load_dotenv
from twitter_client import post_ip_minted_tweet

# Load environment variables from .env file
load_dotenv()

async def test_full_twitter_flow():
    """Simulate the full flow of generating an image, minting IP, and posting to Twitter"""
    print("=== Story IP Creator - Twitter Flow Test ===")
    print("This script simulates the full flow of generating an image, minting IP, and posting to Twitter.")
    
    # Check if required environment variables are set
    required_vars = [
        "TWITTER_USERNAME", 
        "TWITTER_PASSWORD",
        "TWITTER_EMAIL"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please make sure these are set in your .env file")
        return False
    
    try:
        # Step 1: Simulate image generation
        print("\n1. Generating image...")
        # For testing, we'll use a placeholder image URL
        image_url = "https://picsum.photos/512/512"  # Random placeholder image
        print(f"Image generated: {image_url}")
        
        # Step 2: Simulate IP minting
        print("\n2. Minting IP asset...")
        # Generate a random IP ID and transaction hash
        ip_id = f"SP-IP-{random.randint(1000, 9999)}"
        tx_hash = "0x" + "".join(random.choice("0123456789abcdef") for _ in range(64))
        print(f"IP asset minted with ID: {ip_id}")
        print(f"Transaction hash: {tx_hash}")
        
        # Step 3: Post to Twitter
        print("\n3. Posting to Twitter...")
        result = await post_ip_minted_tweet(ip_id, tx_hash, image_url)
        
        # Check the result
        if result.get("success"):
            print(f"\n✅ Successfully posted to Twitter!")
            print(f"Message: {result.get('message')}")
            return True
        else:
            print(f"\n❌ Failed to post to Twitter: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_full_twitter_flow())
