# No-Generic-Replies Upgrade

## Overview
This upgrade prevents the Reddit bot from posting generic, off-topic replies like "This looks great! Thanks for sharing your work!" when it doesn't have anything meaningful to contribute. Instead, the bot will skip posts where it cannot generate an appropriate, on-topic response.

## Key Changes

### 1. Removed Generic Fallbacks
- Eliminated the generic fallback string in `groq_wrapper.py`
- Now returns `None` when an error occurs or when Groq returns nothing
- Added detection for "SKIP" responses from the LLM

### 2. Added Topicality Check
- New `is_on_topic()` helper method in `RedditBot` class
- Uses lightweight keyword matching to ensure replies are relevant to the post
- Checks for shared keywords between post and reply
- Rejects replies with generic patterns like "thanks for sharing"

### 3. Updated Reply Handling
- Modified `generate_reply()` to run both sentiment and topicality checks
- Updated `reply_to_posts()` to skip posts when no appropriate reply can be generated
- Added logging for skipped posts with reason

### 4. Automatic Skip Instruction
Instead of requiring changes to each bot's prompt in Supabase, the skip instruction is now automatically added in the code:

- For default prompts: Added directly to the system message template
- For custom prompts: Appended to the system message if not already present

This approach means:
- No need to update individual bot prompts in Supabase
- Consistent behavior across all bots
- Centralized control of the skip instruction

## Expected Behavior
- The bot will comment less frequently but with higher quality, more relevant responses
- Posts where the bot can't generate a meaningful response will be skipped
- The interaction log will track skipped posts with the reason "Failed sentiment/topic check"
- Karma should improve as the bot avoids posting inappropriate generic comments

## Implementation Notes
- No workflow changes are needed - the GitHub Actions remain the same
- The bot will discover subreddits as before, using both keywords and fixed_subs
- The `fallback_reply` column in Supabase is no longer used but can remain for future use
