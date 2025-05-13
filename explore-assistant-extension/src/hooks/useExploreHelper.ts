import { useContext, useState } from 'react'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { v4 as uuidv4 } from 'uuid'
import { useExploreSelection } from './useExploreSelection'

interface ApiExplore {
  model_name: string;
  name: string;
  description: string;
  label: string;
}

interface RankedExplore {
  selected_explore: {
    model_name: string;
    name: string;
  };
  explanation: string;
}

export const useExploreHelper = () => {
  const { core40SDK, extensionSDK } = useContext(ExtensionContext)
  const dispatch = useDispatch()
  const [isLoading, setIsLoading] = useState(false)
  const { settings } = useSelector((state: RootState) => state.assistant)
  const { ensureExploreSelectionTable } = useExploreSelection()
  
  // The model name from settings
  const modelName = settings?.bigquery_example_looker_model_name?.value 
    ? String(settings.bigquery_example_looker_model_name.value)
    : 'explore_assistant'
  
  // Function to get all available explores from Looker
  const getAvailableExplores = async (): Promise<ApiExplore[]> => {
    setIsLoading(true)
    try {
      // Fetch all LookML models
      const models = await core40SDK.ok(core40SDK.all_lookml_models())
      
      const explores: ApiExplore[] = []
      
      // Extract all explores from all models
      for (const model of models) {
        const modelName = model.name
        if (!model.explores || model.explores.length === 0) {
          continue
        }
        
        for (const explore of model.explores) {
          explores.push({
            model_name: modelName,
            name: explore.name || "",
            description: explore.description || "",
            label: explore.label || explore.name || ""
          })
        }
      }
      
      setIsLoading(false)
      return explores
    } catch (error) {
      console.error('Error fetching explores:', error)
      setIsLoading(false)
      return []
    }
  }
  
  // Function to get explores from the explores table in BigQuery
  const getExploresFromTable = async (): Promise<ApiExplore[]> => {
    setIsLoading(true)
    try {
      // Ensure the explore selection table exists
      await ensureExploreSelectionTable()
      
      // Query for popular explores
      const response = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explores",
            fields: [
              "explores.model_name", 
              "explores.explore_name", 
              "explores.description",
              "explores.popularity_score"
            ],
            sorts: ["explores.popularity_score desc"],
            limit: "100"
          }
        })
      )
      
      // Map the results to the ApiExplore interface
      const explores = response.map(item => ({
        model_name: item["explores.model_name"],
        name: item["explores.explore_name"],
        description: item["explores.description"] || "",
        label: item["explores.explore_name"].replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
      }))
      
      setIsLoading(false)
      return explores
    } catch (error) {
      console.error('Error fetching explores from table:', error)
      setIsLoading(false)
      return []
    }
  }
  
  // Function to populate the explores table
  const populateExploresTable = async (): Promise<boolean> => {
    setIsLoading(true)
    try {
      // Check if the table exists and has data
      const checkResult = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explores",
            fields: ["explores.id"],
            limit: "1"
          }
        })
      )
      
      // If data already exists, return true
      if (checkResult && checkResult.length > 0) {
        setIsLoading(false)
        return true
      }
      
      // Get all explores from Looker API
      const explores = await getAvailableExplores()
      
      if (explores.length === 0) {
        setIsLoading(false)
        return false
      }
      
      // Pull history data from Looker if available
      const historyData = await fetchLookerHistory()
      
      // Process history to get popularity scores
      const popularityScores = processHistoryToPopularityScores(historyData)
      
      // Insert each explore into the table
      for (const explore of explores) {
        const id = uuidv4()
        const popularityScore = popularityScores[`${explore.model_name}.${explore.name}`] || 0
        
        await core40SDK.ok(
          core40SDK.run_inline_query({
            result_format: 'json',
            body: {
              model: modelName,
              view: "explores_upsert",
              fields: ["explores_upsert.status"],
              parameters: {
                id: id,
                model_name: explore.model_name,
                explore_name: explore.name,
                description: explore.description,
                label: explore.label,
                popularity_score: popularityScore.toString(),
                created_at: new Date().toISOString()
              }
            }
          })
        )
      }
      
      setIsLoading(false)
      return true
    } catch (error) {
      console.error('Error populating explores table:', error)
      setIsLoading(false)
      return false
    }
  }
  
  // Function to fetch history data from Looker
  const fetchLookerHistory = async () => {
    try {
      // Fetch recent history data
      const history = await core40SDK.ok(
        core40SDK.all_history({
          fields: "query,history_id,dashboard_id,look_id,explore_url,model,view",
          limit: "5000"
        })
      )
      
      return history
    } catch (error) {
      console.error('Error fetching Looker history:', error)
      return []
    }
  }
  
  // Process history to calculate popularity scores
  const processHistoryToPopularityScores = (historyData: any[]) => {
    const scores: { [key: string]: number } = {}
    
    for (const item of historyData) {
      if (item.explore_url) {
        // Extract model and explore from URL if possible
        const urlParams = new URLSearchParams(item.explore_url.split('?')[1] || '')
        const qid = urlParams.get('qid')
        
        if (item.model && (item.view || qid)) {
          const exploreKey = `${item.model}.${item.view || qid}`
          scores[exploreKey] = (scores[exploreKey] || 0) + 1
        }
      }
    }
    
    return scores
  }
  
  // Function to use AI to rank explores based on user query
  const rankExploresByRelevance = async (
    userQuery: string, 
    explores: ApiExplore[]
  ): Promise<ApiExplore[]> => {
    if (!explores || explores.length === 0) {
      return []
    }
    
    // If Vertex AI settings not available or only one explore, return as is
    if (!settings.vertex_project?.value || !settings.vertex_model?.value || explores.length === 1) {
      return explores
    }
    
    try {
      setIsLoading(true)
      
      const exploreDescriptions = explores.map(explore => 
        `- Model: ${explore.model_name}, Explore: ${explore.name}, ` +
        `Label: ${explore.label}, Description: ${explore.description}`
      ).join("\\n")
      
      const prompt = `
        Given a user's data question and a list of available Looker explores, 
        determine which explore would be most appropriate for answering the question.
        
        User question: ${userQuery}
        
        Available Explores:
        ${exploreDescriptions}
        
        Return your answer as a JSON object with the following structure:
        {
            "selected_explore": {
                "model_name": "name_of_the_model",
                "name": "name_of_the_explore"
            },
            "explanation": "Brief explanation of why this explore was selected"
        }
      `
      
      // Use Vertex AI through the extension SDK
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
      let responseText = ''
      
      if (responseData.predictions && responseData.predictions[0] && responseData.predictions[0].content) {
        responseText = responseData.predictions[0].content
      }
      
      // Try to parse JSON from the response
      const jsonMatch = responseText.match(/({[\s\S]*?})/)
      
      if (jsonMatch) {
        try {
          const result = JSON.parse(jsonMatch[0]) as RankedExplore
          
          // Find the matching explore in our list
          const selectedExplore = explores.find(
            e => e.model_name === result.selected_explore.model_name && 
                e.name === result.selected_explore.name
          )
          
          if (selectedExplore) {
            setIsLoading(false)
            return [selectedExplore, ...explores.filter(e => e !== selectedExplore)]
          }
        } catch (e) {
          console.error('Error parsing AI response:', e)
        }
      }
      
      // If we couldn't get a valid response, return the original list
      setIsLoading(false)
      return explores
      
    } catch (error) {
      console.error('Error ranking explores:', error)
      setIsLoading(false)
      return explores
    }
  }
  
  // Function to select the best explore for a user query
  const selectExploreForQuery = async (userQuery: string) => {
    setIsLoading(true)
    try {
      // Try to get explores from table first
      let explores = await getExploresFromTable()
      
      // If no explores from table, try to populate the table
      if (explores.length === 0) {
        await populateExploresTable()
        explores = await getExploresFromTable()
      }
      
      // If still no explores, get directly from API
      if (explores.length === 0) {
        explores = await getAvailableExplores()
      }
      
      if (explores.length === 0) {
        setIsLoading(false)
        return { success: false, message: "No explores found" }
      }
      
      // Rank explores by relevance to the user's query
      const rankedExplores = await rankExploresByRelevance(userQuery, explores)
      
      if (rankedExplores.length === 0) {
        setIsLoading(false)
        return { 
          success: false, 
          message: "Failed to rank explores" 
        }
      }
      
      // Return the top-ranked explore
      const selectedExplore = rankedExplores[0]
      
      setIsLoading(false)
      return { 
        success: true, 
        explore: {
          modelName: selectedExplore.model_name,
          exploreId: selectedExplore.name,
          exploreKey: `${selectedExplore.model_name}:${selectedExplore.name}`
        },
        message: `Selected explore '${selectedExplore.name}' from model '${selectedExplore.model_name}'`
      }
      
    } catch (error) {
      console.error('Error selecting explore for query:', error)
      setIsLoading(false)
      return { success: false, message: `Error selecting explore: ${error}` }
    }
  }
  
  return { 
    isLoading,
    getAvailableExplores,
    getExploresFromTable,
    populateExploresTable,
    selectExploreForQuery
  }
}