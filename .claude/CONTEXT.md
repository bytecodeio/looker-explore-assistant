# Looker Explore Assistant - Context for AI Assistants

## Project Overview

A Looker extension that enables natural language querying of data using LLMs (Vertex AI) combined with Looker's semantic modeling layer.

**Last Updated**: 2025-01-22
**Current Branch**: single_page_simple

## Architecture

### Components

1. **Frontend Extension** (`explore-assistant-extension/`)
   - React + TypeScript single-page application
   - Runs as a Looker Extension Framework app
   - Communicates with backend via REST API
   - No embedded explores or area selection UI

2. **Backend API** (`explore-assistant-cloud-function/`)
   - Python REST API deployed on Google Cloud Run
   - Uses Vertex AI (Gemini models) for LLM capabilities
   - BigQuery Vector Search for semantic field lookup
   - Olympic system for query history/analytics

3. **Supporting Components**
   - BigQuery for storage (examples, golden queries, vector embeddings)
   - Google Cloud Secret Manager for API key storage
   - Looker SDK for metadata and query execution

## Authentication Architecture

### Current (Simplified) Authentication

**Type**: API Key Authentication

**Flow**:
```
Frontend ’ X-API-Key header ’ Backend
         + user info in body
                                “
                         Validate API key
                                “
                         Extract user info (unverified)
                                “
                         Process query
```

**Key Files**:
- `explore-assistant-cloud-function/core/api_key_auth.py` - API key validation
- `explore-assistant-cloud-function/core/auth.py` - CORS utilities only
- `explore-assistant-extension/src/hooks/useSendCloudRunMessage.ts` - Main API client

**User Identity**:
- Extracted from Looker Extension SDK (`email`, `id`, `display_name`)
- Included in request body for audit purposes
- NOT verified by backend (trust-based)
- Used only for logging in Olympic system

**Setup**:
- Run `./setup_api_key.sh --project <gcp-project>` to generate keys
- API key stored in `.env` files (frontend and backend)
- Production: API key stored in Google Cloud Secret Manager

### Removed (Previous) Authentication

- L OAuth-based authentication with JWT tokens
- L Bearer token authentication
- L JWT decoding/validation logic

## Key Simplifications (Recent Changes)

### Removed Features

1. **MCP System** (Model Context Protocol)
   - Entire `mcp-wrapper/` directory deleted
   - All MCP integration files removed from backend
   - Files: `looker_mcp_server.py`, `field_lookup_mcp.py`, `olympic_mcp_integration.py`, etc.

2. **OAuth/JWT Authentication**
   - Replaced with simple API key validation
   - Removed JWT decoding logic
   - Removed `test_jwt_extraction.py`

3. **Areas Concept**
   - Removed area-based explore organization
   - Deleted `useAreas.ts` hook
   - Queries now automatically determine correct explore via LLM

4. **Embedded Explore Views**
   - Removed `ExploreEmbed.tsx` component
   - Extension no longer embeds Looker explores
   - Users click through to Looker for full explore experience

5. **BigQuery Examples Hook**
   - Removed `useBigQueryExamples.ts`
   - Examples now loaded via backend API

## Current Frontend Architecture

### Main Components

- `src/App.tsx` - Root application component
- `src/pages/AgentPage/index.tsx` - Main chat interface
- `src/pages/QueryPromotionPage/index.tsx` - Query promotion UI
- `src/components/SamplePrompts.tsx` - Sample prompt display

### Key Hooks

| Hook | Purpose |
|------|---------|
| `useSendCloudRunMessage.ts` | Main API communication with backend |
| `useFeedback.ts` | Submit positive/negative feedback |
| `useSystemStatus.ts` | Check backend health status |
| `useOlympicMigration.ts` | Olympic system integration |
| `useVectorSearchSetup.ts` | Vector search table management |
| `useQueryPromotion.ts` | Promote queries to golden/silver |
| `useGenerateBronzeQueries.ts` | Generate bronze tier queries |
| `useOlympicQueries.ts` | Fetch query history from Olympic |
| `useSamplePrompts.ts` | Load sample prompts from backend |
| `useURLParameters.ts` | Handle URL-based navigation |

### State Management

- Redux Toolkit (`src/slices/assistantSlice.ts`)
- localStorage for conversation history
- No settings or configuration UI

## Backend Architecture

### Main Modules

- `restful_backend.py` - Flask REST API server
- `core/auth.py` - CORS utilities (auth logic removed)
- `core/api_key_auth.py` - API key validation
- `core/olympic_service.py` - Olympic system integration
- `core/system_status.py` - System health checks
- `explore_selection/determine.py` - Explore selection logic
- `parameter_generation/generator.py` - Query parameter generation
- `vector_search/` - Vector search integration

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/query` | POST | Main query processing |
| `/api/v1/vertex-proxy` | POST | Vertex AI proxy |
| `/api/v1/feedback/positive` | POST | Positive feedback |
| `/api/v1/feedback/negative` | POST | Negative feedback |
| `/api/v1/feedback` | GET | Get feedback history |
| `/api/v1/debug/test` | GET | Debug endpoint |
| `/api/v1/system/status` | GET | System health |
| `/api/v1/olympic/*` | Various | Olympic system routes |

### Authentication Middleware

All endpoints validate API key via:
```python
from core.api_key_auth import validate_api_key

api_key = request.headers.get('X-API-Key', '')
if not validate_api_key(api_key):
    raise RestfulBackendError("Invalid or missing API key", 401)
```

## Development Workflow

### Local Development

**Backend**:
```bash
cd explore-assistant-cloud-function
export API_SECRET_KEY="your-key"
python restful_backend.py
```

**Frontend**:
```bash
cd explore-assistant-extension
npm install
npm run develop
```

### Testing

**Integration Tests**:
```bash
cd explore-assistant-cloud-function
python tests/run_integration_tests.py --api-key "your-key" --suite quick
```

**Frontend Tests**:
```bash
cd explore-assistant-extension
npm test
```

### Deployment

**Setup API Key**:
```bash
./setup_api_key.sh --project <gcp-project-id>
```

**Deploy Backend**:
```bash
cd explore-assistant-cloud-function
gcloud run deploy explore-assistant-backend \
  --source . \
  --update-secrets=API_SECRET_KEY=explore-assistant-api-key:latest \
  --region us-central1
```

**Deploy Frontend**:
```bash
cd explore-assistant-extension
npm run build
# Upload to Looker project and commit
```

## Important Notes for AI Assistants

### When Making Changes

1. **Authentication**: Always use `X-API-Key` header, never `Authorization: Bearer`
2. **User Info**: User identity comes from request body, not from JWT/token
3. **No MCP**: Don't reference or try to integrate MCP system
4. **No Areas**: Queries determine explores automatically via LLM
5. **No Embedded Explores**: Extension doesn't embed Looker explores

### Common Pitfalls

- L Don't add OAuth/JWT logic back
- L Don't reference `identityToken` or `auth_header` parameters
- L Don't try to decode JWT tokens
- L Don't use `Authorization` header (use `X-API-Key`)
- L Don't create area selection UI
- L Don't embed explores in the extension

### File Locations

**Environment Files**:
- Frontend: `explore-assistant-extension/.env`
- Backend: `explore-assistant-cloud-function/.env`

**Configuration**:
- Frontend: `explore-assistant-extension/src/config/index.ts`
- Backend: Environment variables (no config files)

**Documentation**:
- Main: `README.md`
- Frontend: `explore-assistant-extension/README.md`
- API Key: `API_KEY_SETUP.md`
- Auth Refactor: `AUTHENTICATION_REFACTOR_SUMMARY.md`
- Frontend Migration: `FRONTEND_AUTH_MIGRATION_SUMMARY.md`
- Integration Tests: `explore-assistant-cloud-function/tests/README.md`

## Git Repository

- **Main Branch**: (not specified - check git config)
- **Current Branch**: `single_page_simple`
- **Recent Commits**: Focus on simplification and OAuth removal

### Staged Changes Summary

- Modified: ~30 files (auth refactoring, UI simplification)
- Deleted: ~35 files (MCP system, OAuth logic, areas, ExploreEmbed)
- Added: API key auth, simplified hooks, URL parameters

## Technology Stack

### Frontend
- React 18
- TypeScript
- Redux Toolkit
- Tailwind CSS
- Looker Extension SDK
- Webpack 5

### Backend
- Python 3.9+
- Flask
- Google Cloud SDK
- Vertex AI (Gemini)
- BigQuery
- Looker Python SDK

### Infrastructure
- Google Cloud Run
- Google Cloud Secret Manager
- BigQuery (storage + vector search)
- Google Cloud Storage (optional)

## Vector Search

The system uses BigQuery Vector Search for semantic field lookup:
- Embeddings generated for all Looker fields
- Stored in BigQuery table with vector columns
- Uses `textembedding-gecko` model for embedding generation
- Searches executed via BigQuery SQL with vector similarity functions

## Olympic System

Backend integration for query tracking and analytics:
- Stores all queries and responses
- Tracks user interactions
- Provides golden/silver/bronze query tiers
- Used for training and improvement

## Security Considerations

1. **API Key**: Shared key across all users, visible in frontend bundle
2. **Network Security**: Should use Cloud Run IAM or VPC for additional protection
3. **User Identity**: Unverified, used only for audit purposes
4. **Key Rotation**: Run `./setup_api_key.sh` to generate new keys

## Future Considerations

- Potential for user-specific authentication
- Rate limiting on backend
- Caching layer for common queries
- Enhanced vector search with filtering
