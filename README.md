# meAI Backend - Personal AI Assistant

meAI Backend is the server-side component of a personal AI assistant platform. It provides APIs and real-time communication for managing user conversations, integrating with external toolkits (like Google Calendar, Notion, Slack, Gmail, and more), and leveraging large language models (LLMs) for intelligent task execution. The backend is built with FastAPI and supports both REST and Socket.IO-based real-time streaming.

**Frontend Repository:** [meAI Frontend](https://github.com/2k4sm/meai-fe)

## Features

- User authentication via Google OAuth
- Conversation and message management
- Real-time conversation streaming using Socket.IO
- Integration with external toolkits via Composio
- LLM-powered responses and semantic search using embeddings
- Persistent storage with PostgreSQL and ChromaDB
- Modular, extensible codebase

## Technologies Used

- **FastAPI**: Web framework for building APIs
- **Socket.IO (python-socketio)**: Real-time, bidirectional communication for conversation streaming
- **SQLAlchemy**: ORM for PostgreSQL database access
- **Alembic**: Database migrations
- **ChromaDB**: Vector database for storing and searching message embeddings
- **LangChain**: LLM orchestration and embeddings (supports OpenAI and Google Gemini)
- **Composio**: Unified toolkit integration (Google Calendar, Notion, Slack, Gmail, Google Tasks, Twitter)
- **Authlib**: OAuth client for Google authentication
- **Pydantic**: Data validation and settings management
- **Docker & Docker Compose**: Containerized deployment and local development

## Setup and Installation

### Prerequisites
- Python 3.11+
- Docker and Docker Compose (for local development)
- PostgreSQL and ChromaDB (can be run via Docker Compose)

### Environment Variables
Create a `.env` file in the project root with the following variables (see `app/config.py` for all options):

```
# Application
APP_NAME=
APP_VERSION=
DEBUG=
ENVIRONMENT=

# Database
DATABASE_URL=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=

# ChromaDB (Vector Store)
CHROMA_HOST=
CHROMA_PORT=

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

# JWT & Session
JWT_SECRET_KEY=
JWT_ALGORITHM=
ACCESS_TOKEN_EXPIRE_MINUTES=
REFRESH_TOKEN_EXPIRE_DAYS=
SECRET_KEY=

# LLM Providers
GOOGLE_API_KEY=
OPENAI_API_KEY=
MODEL=

# Composio (Toolkit Integrations)
COMPOSIO_API_KEY=
GOOGLE_CALENDAR_AUTH_CONFIG_ID=
NOTION_AUTH_CONFIG_ID=
GMAIL_AUTH_CONFIG_ID=
GOOGLE_TASKS_AUTH_CONFIG_ID=
SLACKBOT_AUTH_CONFIG_ID=
TWITTER_AUTH_CONFIG_ID=

# CORS
ALLOWED_ORIGIN=

# Cookies
COOKIE_NAME=
COOKIE_MAX_AGE=
COOKIE_PATH=
COOKIE_DOMAIN=
COOKIE_SECURE=
COOKIE_HTTPONLY=
COOKIE_SAMESITE=

# Frontend
FRONTEND_URL=
```

### Running with Docker Compose

1. Build and start all services:
   ```
   docker compose up --build
   ```
2. The backend API will be available at `http://localhost:8080`.
3. PostgreSQL will be available at port 5432, ChromaDB at port 8000.

### Running Locally (without Docker)

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Ensure PostgreSQL and ChromaDB are running and accessible.
3. Set up your `.env` file as described above.
4. Run database migrations:
   ```
   alembic upgrade head
   ```
5. Start the server:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8080
   ```

## API Overview

### Authentication
- `GET /auth/google` - Start Google OAuth login
- `GET /auth/google/callback` - OAuth callback
- `GET /auth/me` - Get current user info (requires session cookie)
- `POST /auth/logout` - Logout user

### Conversations
- `GET /conversations/` - List user conversations
- `POST /conversations/` - Create a new conversation
- `GET /conversations/{conversation_id}/messages` - Get messages in a conversation
- `PATCH /conversations/{conversation_id}` - Update conversation title
- `DELETE /conversations/{conversation_id}` - Delete a conversation
- `DELETE /conversations/{conversation_id}/messages/{message_id}` - Delete a message

### Toolkits and Tools
- `GET /toolkits/` - List supported toolkits
- `POST /toolkits/connect/{toolkit_slug}` - Initiate OAuth connection for a toolkit
- `POST /toolkits/enable/{toolkit_slug}` - Enable a toolkit for the user
- `DELETE /toolkits/disable/{toolkit_slug}` - Disable a toolkit
- `GET /toolkits/connections` - List all toolkit connections for the user
- `GET /toolkits/connections/{toolkit_slug}` - Get connection status for a toolkit
- `POST /toolkits/connections/sync/{connection_request_id}` - Sync a toolkit connection

### Real-Time Streaming
- Socket.IO namespace: `/conversations/stream`
  - Events:
    - `connect` - Authenticate and join
    - `join_conversation` - Join a conversation room
    - `message` - Send a message and receive streamed LLM/tool responses

## Code Structure

- `app/main.py` - FastAPI and Socket.IO app setup, middleware, and router registration
- `app/routers/` - API route handlers (auth, conversations, tools, conversation_sockets)
- `app/models/` - SQLAlchemy ORM models (User, Conversation, Message, UserToolkitConnection)
- `app/schemas/` - Pydantic schemas for API requests and responses
- `app/services/` - Business logic (auth, conversation, LLM, toolkit integration)
- `app/utils/` - Utility functions (auth, embeddings, message handling)
- `app/db/` - Database session and base setup
- `alembic/` - Database migration scripts

## How Technologies Are Used

- **FastAPI** provides the main REST API and dependency injection.
- **Socket.IO** (via `python-socketio`) enables real-time, bidirectional communication for streaming LLM and tool responses to clients.
- **SQLAlchemy** models define users, conversations, messages, and toolkit connections, persisted in PostgreSQL.
- **Alembic** manages database schema migrations.
- **ChromaDB** stores vector embeddings of messages for semantic search and context retrieval.
- **LangChain** orchestrates LLM calls and embeddings, supporting both OpenAI and Google Gemini models.
- **Composio** provides a unified interface to connect and interact with external toolkits (Google Calendar, Notion, Slack, Gmail, Google Tasks, Twitter) via OAuth and API calls.
- **Authlib** handles Google OAuth authentication.
- **Pydantic** is used for data validation and configuration management.
- **Docker Compose** orchestrates the backend, database, and vector store for local development and deployment.

## Database Migrations

- Alembic is used for managing schema migrations.
- Migration scripts are in `alembic/versions/`.
- To create a new migration after model changes:
  ```
  alembic revision --autogenerate -m "Your message"
  alembic upgrade head
  ```
