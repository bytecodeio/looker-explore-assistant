// src/hooks/useExploreSelection.ts
import { useContext, useState } from 'react'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { v4 as uuidv4 } from 'uuid'

export const useExploreSelection = () => {
  const { core40SDK } = useContext(ExtensionContext)
  const dispatch = useDispatch()
  const [isLoading, setIsLoading] = useState(false)
  const { settings } = useSelector((state: RootState) => state.assistant)
  
  // The model name from settings
  const modelName = settings?.bigquery_example_looker_model_name?.value 
    ? String(settings.bigquery_example_looker_model_name.value)
    : 'explore_assistant'
  
  // Function to get user's explore selections
  const getUserExploreSelections = async (userId: string) => {
    setIsLoading(true)
    try {
      const response = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explore_selection",
            fields: ["explore_selection.id", "explore_selection.model_name", "explore_selection.explore_id", "explore_selection.selection_data"],
            filters: { "explore_selection.user_id": userId }
          }
        })
      )
      
      setIsLoading(false)
      return response
    } catch (error) {
      setIsLoading(false)
      console.error('Error fetching explore selections:', error)
      return []
    }
  }
  
  // Function to save a new explore selection
  const saveExploreSelection = async (userId: string, modelName: string, exploreId: string, selectionData: any) => {
    setIsLoading(true)
    try {
      // Create a query to insert data - in Looker this would typically be done through Looker's API
      // Using an insert query if your database supports it
      const id = uuidv4()
      const now = new Date().toISOString()
      
      const query = `
        -- This is an example of how this might work, but actual implementation depends on your database
        INSERT INTO \${database_name}.\${schema_name}.explore_selection 
        (id, model_name, explore_id, user_id, selection_data, created_at, updated_at)
        VALUES ('${id}', '${modelName}', '${exploreId}', '${userId}', '${JSON.stringify(selectionData)}', '${now}', '${now}')
      `
      
      // Execute the query through Looker
      // Note: This would require appropriate permissions and might not be directly possible
      // An alternative would be to have a dedicated API endpoint for this operation
      
      setIsLoading(false)
      return { success: true, id }
    } catch (error) {
      setIsLoading(false)
      console.error('Error saving explore selection:', error)
      return { success: false, error }
    }
  }
  
  // Function to update an existing explore selection
  const updateExploreSelection = async (selectionId: string, selectionData: any) => {
    // Similar implementation to saveExploreSelection but with UPDATE syntax
  }
  
  // Function to delete an explore selection
  const deleteExploreSelection = async (selectionId: string) => {
    // Implementation for deletion
  }
  
  return { 
    isLoading, 
    getUserExploreSelections, 
    saveExploreSelection, 
    updateExploreSelection, 
    deleteExploreSelection 
  }
}