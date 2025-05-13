// src/utils/SetupHelper.ts
import { useContext } from 'react'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { useSelector } from 'react-redux'
import { RootState } from '../store'
import { v4 as uuidv4 } from 'uuid'

export const useSetupHelper = () => {
  const { core40SDK } = useContext(ExtensionContext)
  const { settings } = useSelector((state: RootState) => state.assistant)
  
  // Get the model name from settings
  const modelName = settings?.bigquery_example_looker_model_name?.value 
    ? String(settings.bigquery_example_looker_model_name.value)
    : 'explore_assistant'
  
  /**
   * Initialize explore_selection table using the LookML derived table
   */
  const initExploreSelectionTable = async () => {
    try {
      // Use the explore_selection_create view to create the table
      const result = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explore_selection_create",
            fields: ["explore_selection_create.creation_status"]
          }
        })
      )
      
      return { 
        success: true, 
        message: "Explore selection table initialized successfully" 
      }
    } catch (error) {
      console.error('Error initializing explore selection table:', error)
      return { 
        success: false, 
        error,
        message: `Error initializing explore selection table: ${error}`
      }
    }
  }
  
  /**
   * Initialize explores metadata table using the LookML derived table
   */
  const initExploresTable = async () => {
    try {
      // Use the explores_create view to create the table
      const result = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explores_create",
            fields: ["explores_create.creation_status"]
          }
        })
      )
      
      return { 
        success: true, 
        message: "Explores metadata table initialized successfully" 
      }
    } catch (error) {
      console.error('Error initializing explores metadata table:', error)
      return { 
        success: false, 
        error,
        message: `Error initializing explores metadata table: ${error}`
      }
    }
  }
  
  /**
   * Get query history from Looker's system__activity model
   */
  const getQueryHistory = async (limit = 500) => {
    try {
      // Query Looker's history explore
      const result = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: "system__activity",
            view: "history",
            fields: [
              "query.model",
              "query.view",
              "query.formatted_fields",
              "query.formatted_filters",
              "query.formatted_pivots",
              "query.formatted_sorts",
              "query.runtime",
              "query.client_id",
              "history.created_date",
              "history.dashboard_id"
            ],
            filters: {
              "history.created_date": "90 days",
              "query.model": "-system__activity,-system__embed,-system__internal,-system__lookml_dashboard",
              "query.view": "-NULL"
            },
            sorts: ["history.created_date desc"],
            limit: limit.toString()
          }
        })
      )
      
      console.log(`Retrieved ${result.length} query history entries`)
      return result
    } catch (error) {
      console.error('Error fetching query history:', error)
      return []
    }
  }
  
  /**
   * Group query history by explore
   */
  const groupQueriesByExplore = (historyData: any[]) => {
    const exploreQueries: Record<string, any[]> = {}
    
    for (const entry of historyData) {
      const model = entry["query.model"]
      const view = entry["query.view"]
      
      if (!model || !view) {
        continue
      }
      
      const key = `${model}.${view}`
      
      const queryDetails = {
        fields: entry["query.formatted_fields"] || "",
        filters: entry["query.formatted_filters"] || "",
        pivots: entry["query.formatted_pivots"] || "",
        sorts: entry["query.formatted_sorts"] || "",
        created_date: entry["history.created_date"]
      }
      
      if (!exploreQueries[key]) {
        exploreQueries[key] = []
      }
      
      exploreQueries[key].push(queryDetails)
    }
    
    console.log(`Grouped queries across ${Object.keys(exploreQueries).length} explores`)
    return exploreQueries
  }
  
  /**
   * Analyze explore queries with Vertex AI (similar to the Python function)
   */
  const analyzeExploreQueriesWithLLM = async (
    exploreName: string, 
    modelName: string, 
    queries: any[], 
    maxQueries = 5
  ) => {
    if (!queries || queries.length === 0) {
      return `No historical queries found for ${modelName}.${exploreName}`
    }
    
    // Skip LLM analysis if Vertex AI settings not available
    if (!settings.vertex_project?.value || !settings.vertex_model?.value) {
      return `Explore ${modelName}.${exploreName} contains data related to ${exploreName.replace(/_/g, ' ')}.`
    }
    
    // Limit to most recent queries
    const sampleQueries = queries.slice(0, maxQueries)
    
    // Format the query details for the LLM
    let queryText = ""
    for (let i = 0; i < sampleQueries.length; i++) {
      const query = sampleQueries[i]
      queryText += `Query ${i+1}:\n`
      queryText += `Fields: ${query.fields || 'None'}\n`
      queryText += `Filters: ${query.filters || 'None'}\n`
      queryText += `Sorts: ${query.sorts || 'None'}\n\n`
    }
    
    // Create prompt for the LLM
    const prompt = `
    Analyze the following ${sampleQueries.length} historical Looker queries from the explore "${modelName}.${exploreName}":
    
    ${queryText}
    
    Based on these queries, provide a concise summary (max 200 words) of:
    1. What business questions this explore can answer
    2. The main dimensions and measures people typically analyze
    3. Common filtering patterns
    
    Format the response as a paragraph that would help an analyst understand when to use this explore.
    `
    
    try {
      // Use Vertex AI through the extension SDK
      const { extensionSDK } = useContext(ExtensionContext)
      
      const vertexResponse = await extensionSDK.fetchProxy(
        `https://${settings.vertex_location?.value}-aiplatform.googleapis.com/v1/projects/${settings.vertex_project?.value}/locations/${settings.vertex_location?.value}/publishers/google/models/${settings.vertex_model?.value}:predict`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${settings.oauth2_token?.value}`
          },
          body: JSON.stringify({
            instances: [{ prompt: prompt }]
          })
        }
      )
      
      const responseData = await vertexResponse.json()
      
      if (responseData.predictions && 
          responseData.predictions[0] && 
          responseData.predictions[0].content) {
        return responseData.predictions[0].content
      }
      
      return `Explore ${modelName}.${exploreName} contains data related to ${exploreName.replace(/_/g, ' ')}.`
    } catch (error) {
      console.error(`Error analyzing queries with LLM for ${modelName}.${exploreName}:`, error)
      return `Explore ${modelName}.${exploreName} contains data related to ${exploreName.replace(/_/g, ' ')}.`
    }
  }
  
  /**
   * Populate explores table with data from Looker's API and history
   */
  const populateExploresTable = async () => {
    try {
      // First ensure the table exists
      await initExploresTable()
      
      // Get query history
      const historyData = await getQueryHistory(500)
      
      // Group queries by explore
      const exploreQueries = groupQueriesByExplore(historyData)
      
      // Get all LookML models for complete coverage
      const models = await core40SDK.ok(core40SDK.all_lookml_models())
      console.log(`Retrieved ${models.length} LookML models`)
      
      // Process each model and explore
      for (const model of models) {
        const modelName = model.name
        if (!modelName) continue
        
        // Skip system models
        if (modelName.startsWith('system__') || modelName.startsWith('i__')) {
          continue
        }
        
        try {
          // Get model details
          const modelDetail = await core40SDK.ok(core40SDK.lookml_model(modelName))
          const explores = modelDetail.explores || []
          
          for (const explore of explores) {
            const exploreName = explore.name
            if (!exploreName) continue
            
            // Skip system explores
            if (exploreName.startsWith('system__') || exploreName.startsWith('i__')) {
              continue
            }
            
            // Get the explore's historical queries
            const key = `${modelName}.${exploreName}`
            const queries = exploreQueries[key] || []
            
            try {
              // Fetch detailed explore metadata
              const exploreDetail = await core40SDK.ok(
                core40SDK.lookml_model_explore({
                  lookml_model_name: modelName,
                  explore_name: exploreName,
                  fields: 'fields'
                })
              )
              
              // Extract fields as JSON
              const fields: any = {}
              if (exploreDetail.fields) {
                if (exploreDetail.fields.dimensions) {
                  fields.dimensions = exploreDetail.fields.dimensions.map(d => d.name)
                }
                if (exploreDetail.fields.measures) {
                  fields.measures = exploreDetail.fields.measures.map(m => m.name)
                }
                if (exploreDetail.fields.filters) {
                  fields.filters = exploreDetail.fields.filters.map(f => f.name)
                }
              }
              
              // Get existing description
              let description = exploreDetail.description || ''
              
              // If we have query history, analyze it with the LLM
              if (queries && queries.length > 0) {
                const llmDescription = await analyzeExploreQueriesWithLLM(
                  exploreName, 
                  modelName, 
                  queries
                )
                
                // Combine existing description with LLM analysis
                if (description) {
                  description = `${description}\n\nBased on query history: ${llmDescription}`
                } else {
                  description = `Based on query history: ${llmDescription}`
                }
              }
              
              // Create row with usage statistics
              let lastUsed = null
              if (queries && queries.length > 0) {
                try {
                  const createdDate = queries[0].created_date
                  if (createdDate) {
                    lastUsed = createdDate
                  } else {
                    lastUsed = new Date().toISOString()
                  }
                } catch (e) {
                  console.warn(`Error formatting timestamp: ${e}, using current time`)
                  lastUsed = new Date().toISOString()
                }
              }
              
              // Insert data using the explores_upsert view
              await core40SDK.ok(
                core40SDK.run_inline_query({
                  result_format: 'json',
                  body: {
                    model: modelName,
                    view: "explores_upsert",
                    fields: ["explores_upsert.status"],
                    parameters: {
                      id: `${modelName}_${exploreName}`,
                      model_name: modelName,
                      explore_name: exploreName,
                      description: description.slice(0, 1000), // Limit description length
                      label: explore.label || exploreName,
                      popularity_score: (queries ? queries.length : 0).toString(),
                      fields_json: JSON.stringify(fields),
                      last_used: lastUsed || new Date().toISOString(),
                      usage_count: (queries ? queries.length : 0).toString(),
                      created_at: new Date().toISOString()
                    }
                  }
                })
              )
              
              console.log(`Successfully processed explore ${modelName}.${exploreName}`)
              
            } catch (exploreError) {
              console.warn(`Error processing explore ${modelName}.${exploreName}:`, exploreError)
              continue
            }
          }
          
        } catch (modelError) {
          console.warn(`Error processing model ${modelName}:`, modelError)
          continue
        }
      }
      
      return { 
        success: true, 
        message: "Successfully populated explores table" 
      }
    } catch (error) {
      console.error('Error populating explores table:', error)
      return { 
        success: false, 
        error,
        message: `Error populating explores table: ${error}`
      }
    }
  }
  
  /**
   * Check if a table exists and how many rows it has
   */
  const checkTableRowCount = async (tableName: string) => {
    try {
      // Query for the count of rows in the table
      const response = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: tableName,
            fields: [`${tableName}.count`],
            limit: "1"
          }
        })
      )
      
      if (response && response.length > 0) {
        const count = response[0][`${tableName}.count`]
        return { 
          exists: true, 
          rowCount: count,
          message: `Table ${tableName} exists with ${count} rows` 
        }
      }
      
      return { exists: true, rowCount: 0, message: `Table ${tableName} exists but has no rows` }
    } catch (error) {
      console.error(`Error checking table ${tableName}:`, error)
      return { exists: false, rowCount: 0, message: `Error or table ${tableName} does not exist` }
    }
  }
  
  return {
    initExploreSelectionTable,
    initExploresTable,
    populateExploresTable,
    checkTableRowCount,
    getQueryHistory
  }
}