# Quick Start Guide

## Test the Server Locally

1. **Run the test script** to verify everything works:
```bash
uv run python test_server.py
```

This will:
- Initialize the vector database
- Add sample dimension values
- Test semantic search functionality
- Show example results

## Start the MCP Server

2. **Start the MCP server** for use with AI assistants:
```bash
uv run python server.py
```

The server will start and be ready to accept MCP connections.

## Connect to Claude Desktop

3. **Add to your Claude Desktop configuration**:

Edit your Claude Desktop config file and add:
```json
{
  "mcpServers": {
    "looker-vector-search": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "/home/colin/looker-explore-assistant/explore-assistant-vector-mcp"
    }
  }
}
```

## Example Usage in Claude

Once connected, you can use these tools in Claude:

```
Claude, can you search for dimension values related to "product categories"?
```

Claude will use the `search_dimension_values` tool to find matching fields.

## Adding Your Own Data

To add your Looker dimension values:

```python
add_dimension_values([
    {
        "value": "Your Dimension Value",
        "field_reference": "model.explore.view.field", 
        "explore_key": "model:explore",
        "field_type": "dimension",
        "description": "Description of the field"
    }
])
```

## Next Steps

- Populate with your actual Looker dimension values
- Integrate with existing Looker data extraction scripts
- Connect to multiple AI assistants via MCP