-- Migration SQL for adding subreddit rotation features
-- This file only adds new tables and doesn't modify existing data

-- Create a table to track subreddit interaction history
CREATE TABLE IF NOT EXISTS subreddit_history (
  bot_id           text,
  subreddit        text,
  last_commented_at timestamp DEFAULT now(),
  PRIMARY KEY (bot_id, subreddit)
);

-- Create a global table for excluded subreddits (opt-out list)
CREATE TABLE IF NOT EXISTS excluded_subreddits (
  subreddit        text PRIMARY KEY,          -- subreddit name to exclude
  reason           text,                      -- optional reason for exclusion
  added_at         timestamp DEFAULT now()    -- when it was added to the exclusion list
);

-- Add bot_type column to reddit_bots table if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'reddit_bots' AND column_name = 'bot_type'
  ) THEN
    ALTER TABLE reddit_bots ADD COLUMN bot_type text DEFAULT 'general';
    
    -- Set initial bot types based on bot_id
    UPDATE reddit_bots SET bot_type = 'logistics' WHERE id LIKE 'logistics%';
    UPDATE reddit_bots SET bot_type = 'slime' WHERE id LIKE 'slime%';
  END IF;
END $$;

-- Example data for excluded subreddits (you can modify this list)
INSERT INTO excluded_subreddits (subreddit, reason) VALUES
('politics', 'Controversial topics'),
('news', 'Too much negativity'),
('worldnews', 'Too much negativity'),
('conspiracy', 'Controversial topics'),
('unpopularopinion', 'Controversial topics')
ON CONFLICT (subreddit) DO NOTHING; -- Skip if already exists
