# Explore Assistant Extension Frontend

This documentation outlines the steps required to deploy the Explore Assistant Extension. The extension uses API key authentication to communicate with the backend Cloud Run service.

## Prerequisites

- A GCP project with the backend Cloud Run service deployed
- API key configured (see [API Key Setup](../API_KEY_SETUP.md))
- A Looker instance with extension framework enabled
- Node.js and npm installed for building the extension

## Architecture

The frontend is a single-page React application that:
- Sends natural language queries to the backend REST API
- Displays query results and visualizations
- Maintains conversation history in browser localStorage
- Provides sample prompts organized by use case
- Extracts user identity from Looker SDK for audit purposes

### Authentication

The extension uses **API key authentication**:
- API key is configured via environment variable (`API_KEY`)
- Sent in `X-API-Key` header with all requests
- User identity (email, user_id, display_name) extracted from Looker SDK
- User info included in request body for audit logging (not verified by backend)

## Setup Steps

### 1. Configure Environment

Create a `.env` file in the extension directory:

```bash
cp .env.example .env
```

Edit `.env` and configure:

```bash
# API key for backend authentication (required)
API_KEY=your-api-key-here

# Backend Cloud Run service URL (required)
CLOUD_RUN_SERVICE_URL=https://your-service-url.run.app
```

**Note**: You can generate an API key by running `../setup_api_key.sh --project your-gcp-project`

### 2. Install Dependencies

```bash
npm install
```

### 3. Build the Extension

```bash
npm run build
```

This creates a production build in the `dist/` directory with the API key compiled into the bundle.

### 4. Set Up Looker Project

1. Log in to Looker and create a new project or use an existing project
2. Upload the `manifest.lkml` file from this directory into your Looker project
3. Update `manifest.lkml` with your configuration:
   - Update `application.id` if needed
   - Configure `application.entitlements` based on required permissions
4. Commit your changes through the Looker Project UI

### 5. Deploy the Extension

1. Commit and deploy the project to production in Looker
2. Reload the page and navigate to **Browse** → **Extensions**
3. You should see "Explore Assistant" in the list
4. Click to launch the extension

## Development

### Local Development

For local development with live reload:

```bash
npm run develop
```

This starts a webpack dev server. You'll need to configure Looker to point to your local development server in the `manifest.lkml` file.

### Testing

Run the test suite:

```bash
npm test
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `API_KEY` | API key for backend authentication | Yes |
| `CLOUD_RUN_SERVICE_URL` | Backend Cloud Run service URL | Yes |

### Manifest Configuration

The `manifest.lkml` file configures:
- Extension ID and label
- Required entitlements (core_api_methods, use_embeds, etc.)
- Entry point file

## Features

### Removed from Previous Versions

This simplified version has removed:
- **OAuth authentication** - Now uses API key authentication
- **Area/explore selection UI** - Queries automatically determine the correct explore
- **Embedded explore views** - Extension now only shows query results as data/visualizations
- **Settings management** - Configuration simplified to environment variables

### Current Features

- **Single-page interface** - Streamlined chat-based query interface
- **Query history** - Stored in browser localStorage
- **Sample prompts** - Organized by use case, loaded from backend
- **Multi-turn conversations** - Contextual follow-up questions
- **Query promotion** - Promote queries to "golden" or "silver" status
- **Feedback** - Submit positive/negative feedback on query results

## Troubleshooting

### Extension doesn't load

**Check:**
1. `manifest.lkml` is committed and deployed in Looker
2. Extension framework is enabled in your Looker instance
3. Browser console for JavaScript errors

### Authentication errors (401 Unauthorized)

**Check:**
1. `.env` file exists with correct `API_KEY`
2. API key matches the backend configuration
3. Extension was rebuilt after updating `.env` (`npm run build`)
4. Backend Cloud Run service is running and accessible

### User info not captured

**Check:**
1. Browser console for Looker SDK errors
2. Network tab shows `user_email`, `user_id`, `user_name` in request payload
3. Looker user attributes are populated correctly

## Security Notes

- **API Key Security**: The API key is compiled into the JavaScript bundle and is visible to anyone who inspects the code. Additional security should be provided by network controls (VPC, Cloud Run authentication, etc.)
- **User Identity**: User information from Looker SDK is used for audit purposes only and is not verified by the backend
- **Key Rotation**: Rotate API keys regularly using `../setup_api_key.sh`

## Additional Resources

- [API Key Setup Guide](../API_KEY_SETUP.md)
- [Authentication Refactor Summary](../AUTHENTICATION_REFACTOR_SUMMARY.md)
- [Frontend Auth Migration Summary](../FRONTEND_AUTH_MIGRATION_SUMMARY.md)
- [Backend Integration Tests](../explore-assistant-cloud-function/tests/README.md)
