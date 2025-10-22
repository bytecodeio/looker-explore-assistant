# Looker Explore Assistant

This is an extension or API plugin for Looker that integrates LLMs hosted on Vertex AI into a natural language experience powered by Looker's modeling layer.

![explore assistant](./static/explore-assistant.gif)

## Description

The Explore Assistant allows users to generate Looker Explore queries via natural language, outputting results into visualizations. Rather than writing raw SQL, the LLM translates text inputs into Looker explore queries. This leverages what LLMs excel at - **generative content** - while Looker provides the **underlying data context, metadata and business logic**.

### Key Features

 - **Natural Language Querying** - Generate Looker queries from plain English
 - **Question History** - Stored in browser localstorage for easy reference
 - **Sample Prompts** - Customizable prompts organized by use case
 - **Structured Logging** - Input & output token counts for cost tracking
 - **Multi-turn Conversations** - Contextual follow-up questions
 - **Insight Summarization** - AI-generated insights from query results
 - **Dynamic Explore Selection** - Automatically chooses the right explore based on query intent
 - **Vector Search** - Semantic search for fields and metrics using BigQuery Vector Search

## Architecture

The system consists of three main components:

1. **Frontend Extension** - Looker extension built with React and TypeScript
2. **Backend API** - Python REST API deployed on Google Cloud Run
3. **Vector Search** - BigQuery Vector Search for semantic field lookup

### Authentication Flow

- Frontend uses **API key authentication** (X-API-Key header)
- User identity extracted from Looker SDK for audit logging
- Backend validates API key stored in Google Cloud Secret Manager

### Removed Features

This simplified version has removed:
- OAuth-based authentication (replaced with API keys)
- MCP (Model Context Protocol) system
- Area-based explore organization
- Embedded explore views within the extension

## Setup

Follow these steps in order for successful installation:

1. **Backend Setup** - Deploy the Cloud Run service and configure Vertex AI [using these instructions](./explore-assistant-backend/README.md)
2. **API Key Setup** - Generate and configure API keys [using these instructions](./API_KEY_SETUP.md)
3. **Example Generation** - Generate training examples and upload to BigQuery [using these instructions](./explore-assistant-examples/README.md)
4. **Frontend Setup** - Build and deploy the Looker extension [using these instructions](./explore-assistant-extension/README.md)

### Technologies Used
#### Frontend
- [React](https://reactjs.org/)
- [TypeScript](https://www.typescriptlang.org/)
- [Webpack](https://webpack.js.org/).
- [Tailwind CSS](https://tailwindcss.com/)

#### Looker
- [Looker Extension SDK](https://github.com/looker-open-source/sdk-codegen/tree/main/packages/extension-sdk-react)
- [Looker Embed SDK](https://cloud.google.com/looker/docs/embed-sdk)
- [Looker Components](https://cloud.google.com/looker/docs/components)

#### Backend API
- [Google Cloud Platform](https://cloud.google.com/)
- [Vertex AI](https://cloud.google.com/vertex-ai)
- [Cloud Functions](https://cloud.google.com/functions)

## Recommendations for fine tuning the model

This app uses a one shot prompt technique for fine tuning a model, meaning that all the metadata for the model is contained in the prompt. It's a good technique for a small dataset, but for a larger dataset, you may want to use a more traditional fine tuning approach. This is a simple implementation, but you can also use a more sophisticated approach that involves generating embeddings for explore metadata and leveraging a vector database for indexing.

Any `json` file you see in this repo is used to train the llm with representative Looker Explore Query examples. These examples are used to help the understand how to create different variations of Looker Explore Queries to account for requests that might result in pivots, relative date filters, includes string syntax, etc. For convenience and customization we recommend using Looker System Activity, filtering queries for the model and explore you plan on using the assistant with, and then using the top 20-30 queries as your example input output string with their expanded url syntax. Please see the [Explore Assistant Training Notebook](./explore-assistant-training/) for creating query examples for new datasets via an automated process.
