# Reddit MCP Server

This server provides a comprehensive Multi-Channel Platform (MCP) for interacting with Reddit via API. It enables seamless integration with Reddit's features for various applications including content aggregation, monitoring, and automated interactions.

## Features

### Content Browsing
- Browse posts from any subreddit with customizable sorting and filtering
- View trending and popular content across Reddit
- Search Reddit for specific posts, comments, or topics
- Real-time feed updates for subreddits

### Post & Comment Management
- Create, edit, and delete posts
- Submit comments and replies
- Upvote, downvote, and award content
- Save and bookmark favorite posts
- Rich text formatting support

### User & Account Features
- User profile management and history viewing
- Karma and awards tracking
- Private messaging system
- Friend and follower management
- Multi-account support with secure credential storage

### Subreddit Exploration
- Discover and explore subreddits by category
- View detailed subreddit information and statistics
- Track subreddit growth and engagement metrics
- Monitor moderation activity
- Subreddit rule compliance checking

### Advanced Features
- Content filtering based on keywords, domains, or users
- Scheduled posting and automated interactions
- Custom notification system for specific triggers
- Analytics and reporting on user and subreddit activity
- Rate limiting management to comply with Reddit API policies
- Proxy support for distributed access

## Setup & Configuration

### Prerequisites
- Python 3.8 or higher
- Reddit API credentials (client ID, client secret)
- PRAW library and dependencies

### Installation
1. Clone this repository:
   ```
   git clone <repository-url>
   cd servers/reddit_server
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure your Reddit API credentials:
   Create a `.env` file with the following content:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USERNAME=your_username
   REDDIT_PASSWORD=your_password
   REDDIT_USER_AGENT=your_app_name/1.0
   ```

4. Run the server:
   ```
   python reddit_mcp.py
   ```

### Configuration Options
- `PORT`: Server port (default: 8000)
- `HOST`: Server host (default: 0.0.0.0)
- `DEBUG`: Enable debug mode (default: False)
- `LOG_LEVEL`: Logging level (default: INFO)
- `RATE_LIMIT`: API rate limit management (default: 60 requests per minute)
- `CACHE_EXPIRY`: Cache expiration time (default: 300 seconds)

## Testing

### Unit Tests
Run the complete test suite:
```
python test_reddit_mcp.py
```

### Individual Test Components
Test specific components:
```
python test_reddit_mcp.py TestRedditAPI         # Test API functionality
python test_reddit_mcp.py TestAuthentication    # Test auth mechanisms
python test_reddit_mcp.py TestSubredditFeatures # Test subreddit operations
```

### Integration Testing
Run integration tests with the live Reddit API:
```
python test_reddit_mcp.py --integration
```

### Mock Testing
Test with mock Reddit data:
```
python testreddit.py
```

## Files & Architecture

### Core Components
- `reddit_mcp.py` - Main server implementation with API endpoints
- `test_reddit_mcp.py` - Comprehensive test suite for server functionality
- `testreddit.py` - Mock test utilities and sample data

### Architecture
The Reddit MCP Server follows a layered architecture:

1. **API Layer** - Handles external requests and authentication
2. **Service Layer** - Core business logic for Reddit interactions
3. **Data Layer** - Data processing and persistence
4. **Integration Layer** - Reddit API communication

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/subreddits` | GET | Get list of subreddits |
| `/api/subreddit/{name}` | GET | Get subreddit details |
| `/api/posts` | GET | Get posts from specified subreddit |
| `/api/post/{id}` | GET | Get specific post details |
| `/api/post` | POST | Create a new post |
| `/api/comments/{post_id}` | GET | Get comments for a post |
| `/api/comment` | POST | Add a comment |
| `/api/user/{username}` | GET | Get user profile |
| `/api/search` | GET | Search Reddit content |
| `/api/vote` | POST | Submit a vote |

## Performance Optimization

The server includes several optimization features:

- Content caching for frequently accessed data
- Connection pooling for Reddit API requests
- Batch processing for multiple requests
- Asynchronous processing for non-blocking operations
- Result pagination for handling large datasets
- Rate limiting to prevent API throttling

## Security

- OAuth2 authentication with Reddit
- API key validation for client applications
- Input validation and sanitization
- Rate limiting for abuse prevention
- Secure credential storage
- CORS configuration for web clients

## Deployment

### Docker Deployment
```
docker build -t reddit-mcp-server .
docker run -p 8000:8000 reddit-mcp-server
```

### Kubernetes Deployment
Kubernetes manifests are available in the `k8s/` directory.

### Cloud Deployment
Instructions for AWS, GCP, and Azure deployments are available in the `deployment/` directory.

## Monitoring & Logging

- Structured logging with rotation
- Performance metrics collection
- Health check endpoints
- Error tracking and reporting
- Usage statistics and analytics

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests for your functionality
5. Submit a pull request

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgements

- Reddit API team for documentation and support
- PRAW library developers
- Contributors to the MCP framework
