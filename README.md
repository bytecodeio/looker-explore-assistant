# Looker Explore Assistant

An intelligent assistant that transforms natural language questions into Looker explores, leveraging LLM capabilities to generate insightful data visualizations.

![Workflow Diagram](./docs/images/looker_explore_workflow.png)

## Overview

The Looker Explore Assistant bridges the gap between natural language questions and data analytics by intelligently translating user queries into Looker explore URLs and data visualizations. It combines multiple specialized LLM models with Looker's API to create a seamless experience for data exploration.

## Architecture

The system uses a node-based architecture in a LangChain workflow:

1. **User Query Processing** - Parses and understands user questions
2. **Explore Selection** - Identifies the most relevant Looker explore for the query
3. **Semantic Model Loading** - Retrieves metadata about available fields
4. **Explore Parameters Generation** - Converts the query into structured parameters
5. **Filter Value Fetching** - Enhances filters with real values from the data
6. **Explore Execution** - Runs the generated query and summarizes results

### Model Efficiency Strategy

![Model Selection](./docs/images/model_selection_flow.png)

The system uses different models for different tasks:

- **Fast Model (Gemini Pro)** - For simple classification and text processing tasks
- **Thinking Model (Claude 3.7 Sonnet)** - For complex reasoning and parameter generation
- **Summary Model (Gemini Pro)** - For data summarization with creative insights
- **Filter Model (Gemini Pro)** - For selecting optimal filter values

## Key Features

### Intelligent Explore Selection

The system automatically identifies the most appropriate Looker explore for answering the user's question by analyzing available explores and their metadata.

### Contextual Document Loading

![Document Flow](./docs/images/conditional_document_flow.png)

Documentation is loaded conditionally based on the query requirements:

- Filter documentation is always included
- Visualization documentation is only included for visualization-related queries
- Pivot documentation is only included when pivoting would enhance results

### Smart Filter Enhancement

The system automatically:
- Detects when string-type dimensions need specific values
- Runs small, efficient Looker queries to fetch real values
- Uses LLMs to select the most relevant values for filters

### Explore URL Generation

Every result includes a direct link to the Looker explore, allowing users to:
- View and modify the generated visualization in Looker
- Share the results with colleagues
- Further refine the data exploration

### Comprehensive Data Summarization

Results are provided with insightful summaries that:
- Highlight key findings from the data
- Organize insights into logical sections
- Surface patterns and anomalies

## Installation

### Prerequisites

- Python 3.8+
- Looker SDK
- LangChain
- Access to LLM APIs (Vertex AI, Anthropic)
- Graphviz (for workflow visualization)

### Setup

1. Clone the repository:
