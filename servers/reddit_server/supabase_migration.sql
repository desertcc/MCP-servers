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

-- Example data for excluded subreddits (you can modify this list)
INSERT INTO excluded_subreddits (subreddit, reason) VALUES
('politics', 'Controversial topics'),
('news', 'Too much negativity'),
('worldnews', 'Too much negativity'),
('conspiracy', 'Controversial topics'),
('unpopularopinion', 'Controversial topics')
ON CONFLICT (subreddit) DO NOTHING; -- Skip if already exists
