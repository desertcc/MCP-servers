#!/usr/bin/env python3
"""Reddit Refresh Token Generator

This script helps obtain a refresh token from Reddit for use with the Reddit MCP Automation Bot.
It uses the authorization code flow to get a permanent refresh token.
"""

import os
import sys
import argparse
import praw
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_auth_url():
    """Generate the authorization URL for Reddit OAuth."""
    # Check if we have the required environment variables
    required_vars = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_REDIRECT_URI"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease add the following to your .env file:")
        for var in missing_vars:
            print(f"{var}=your_{var.lower()}")
        sys.exit(1)
    
    try:
        # Initialize the Reddit instance
        reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID"),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
            redirect_uri=os.environ.get("REDDIT_REDIRECT_URI", "http://localhost:8000/reddit/callback"),
            user_agent=os.environ.get("REDDIT_USER_AGENT", "windows:slime_bot:1.0 (by u/Slime_newbie)")
        )
        
        # Generate the authorization URL
        scopes = ["identity", "read", "submit", "vote"]
        state = "uniquestate"
        auth_url = reddit.auth.url(scopes, state, "permanent")
        
        print("\nPlease visit the following URL in your browser to authorize the application:")
        print(f"\n{auth_url}\n")
        print("After authorizing, you'll be redirected to your redirect URI.")
        print("Copy the 'code' parameter from the URL (without the '#_' at the end if present).")
        print("Add it to your .env file as REDDIT_AUTH_CODE=your_code")
        print("Then run this script again without the --get-url flag to obtain a refresh token.")
        
    except Exception as e:
        print(f"Error generating authorization URL: {e}")
        sys.exit(1)

def get_refresh_token():
    """Get a refresh token from Reddit using the authorization code."""
    # Check if we have the required environment variables
    required_vars = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_AUTH_CODE", "REDDIT_REDIRECT_URI"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease add the following to your .env file:")
        for var in missing_vars:
            print(f"{var}=your_{var.lower()}")
        
        if "REDDIT_AUTH_CODE" in missing_vars:
            print("\nTo get your REDDIT_AUTH_CODE, run:")
            print("python get_refresh_token.py --get-url")
        
        sys.exit(1)
    
    try:
        # Clean up the auth code (remove #_ if present)
        auth_code = os.environ.get("REDDIT_AUTH_CODE").split("#")[0]
        
        # Initialize the Reddit instance
        reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID"),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
            redirect_uri=os.environ.get("REDDIT_REDIRECT_URI", "http://localhost:8000/reddit/callback"),
            user_agent=os.environ.get("REDDIT_USER_AGENT", "windows:slime_bot:1.0 (by u/Slime_newbie)")
        )
        
        # Get the refresh token using the authorization code
        refresh_token = reddit.auth.authorize(auth_code)
        
        print("\nSuccess! Your refresh token has been generated.")
        print(f"\nRefresh Token: {refresh_token}")
        print("\nAdd this to your .env file as:")
        print(f"REDDIT_REFRESH_TOKEN={refresh_token}")
        
        # Update the .env file automatically if possible
        try:
            with open(".env", "r") as f:
                env_content = f.read()
            
            if "REDDIT_REFRESH_TOKEN" in env_content:
                # Replace existing refresh token
                with open(".env", "w") as f:
                    env_content = env_content.replace(
                        f"REDDIT_REFRESH_TOKEN={os.environ.get('REDDIT_REFRESH_TOKEN', '')}",
                        f"REDDIT_REFRESH_TOKEN={refresh_token}"
                    )
                    f.write(env_content)
            else:
                # Add new refresh token
                with open(".env", "a") as f:
                    f.write(f"\nREDDIT_REFRESH_TOKEN={refresh_token}")
            
            print("\nYour .env file has been updated automatically.")
        except Exception as e:
            print(f"\nCould not update .env file automatically: {e}")
            print("Please add the refresh token to your .env file manually.")
        
    except Exception as e:
        print(f"Error obtaining refresh token: {e}")
        print("\nPlease check your REDDIT_AUTH_CODE and try again.")
        print("Make sure to remove any '#_' at the end of the code if present.")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reddit Refresh Token Generator")
    parser.add_argument("--get-url", action="store_true", help="Generate the authorization URL")
    args = parser.parse_args()
    
    if args.get_url:
        generate_auth_url()
    else:
        get_refresh_token()
