-- Add DIY and Truckers to the excluded_subreddits table
INSERT INTO excluded_subreddits (subreddit, reason)
VALUES 
('DIY', 'Manual exclusion requested'),
('Truckers', 'Manual exclusion requested')
ON CONFLICT (subreddit) DO NOTHING;

-- Verify the current excluded subreddits
SELECT * FROM excluded_subreddits;
