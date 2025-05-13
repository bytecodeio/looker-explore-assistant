// src/hooks/useExploreSelection.ts
import { useContext, useState } from 'react'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { v4 as uuidv4 } from 'uuid'
import { setExploreSelections, addExploreSelection, updateExploreSelection } from '../slices/assistantSlice'

export interface ExploreSelectionData {
  id?: string
  model_name: string
  explore_id: string
  user_id: string
  selection_data: string | object
  created_at?: string
  updated_at?: string
}

export const useExploreSelection = () => {
  const { core40SDK, extensionSDK } = useContext(ExtensionContext)
  const dispatch = useDispatch()
  const [isLoading, setIsLoading] = useState(false)
  const { settings } = useSelector((state: RootState) => state.assistant)
  
  // The model name from settings
  const modelName = settings?.bigquery_example_looker_model_name?.value 
    ? String(settings.bigquery_example_looker_model_name.value)
    : 'explore_assistant'
  
  // Function to create the explore selection table if it doesn't exist
  const ensureExploreSelectionTable = async () => {
    setIsLoading(true)
    try {
      // Run the explore_selection_create query which uses CREATE TABLE IF NOT EXISTS
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
      
      setIsLoading(false)
      return { success: true, result }
    } catch (error) {
      setIsLoading(false)
      console.error('Error ensuring explore selection table exists:', error)
      return { success: false, error }
    }
  }
  
  // Function to get user's explore selections
  const getUserExploreSelections = async (userId: string) => {
    setIsLoading(true)
    try {
      // First ensure the table exists
      await ensureExploreSelectionTable()
      
      // Now query for the user's selections
      const response = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explore_selection",
            fields: [
              "explore_selection.id", 
              "explore_selection.model_name", 
              "explore_selection.explore_id", 
              "explore_selection.user_id", 
              "explore_selection.selection_data",
              "explore_selection.created_time",
              "explore_selection.updated_time"
            ],
            filters: { "explore_selection.user_id": userId }
          }
        })
      )
      
      // Process the results
      const selections = response.map(item => ({
        id: item["explore_selection.id"],
        modelName: item["explore_selection.model_name"],
        exploreId: item["explore_selection.explore_id"],
        userId: item["explore_selection.user_id"],
        selectionData: JSON.parse(item["explore_selection.selection_data"] || '{}'),
        createdAt: new Date(item["explore_selection.created_time"]).getTime(),
        updatedAt: new Date(item["explore_selection.updated_time"]).getTime()
      }))
      
      // Update Redux store
      dispatch(setExploreSelections(selections))
      
      setIsLoading(false)
      return selections
    } catch (error) {
      setIsLoading(false)
      console.error('Error fetching explore selections:', error)
      return []
    }
  }
  
  // Function to save a new explore selection
  const saveExploreSelection = async (
    modelName: string, 
    exploreId: string, 
    selectionData: any
  ) => {
    setIsLoading(true)
    try {
      // First ensure the table exists
      await ensureExploreSelectionTable()
      
      // Get current user information
      const currentUser = await extensionSDK.lookerHostData?.getCurrentUser?.() || {}
      const userId = currentUser?.id?.toString() || 'unknown_user'
      
      const id = uuidv4()
      const now = new Date().toISOString()
      const selectionDataStr = typeof selectionData === 'string' 
        ? selectionData 
        : JSON.stringify(selectionData)
      
      // Use the upsert operation
      await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explore_selection_upsert",
            fields: ["explore_selection_upsert.status"],
            parameters: {
              id: id,
              model_name: modelName,
              explore_id: exploreId,
              user_id: userId,
              selection_data: selectionDataStr,
              created_at: now
            }
          }
        })
      )
      
      // Create the selection object
      const selection = {
        id,
        modelName,
        exploreId,
        userId,
        selectionData,
        createdAt: new Date(now).getTime(),
        updatedAt: new Date(now).getTime()
      }
      
      // Update Redux store
      dispatch(addExploreSelection(selection))
      
      setIsLoading(false)
      return { success: true, id, selection }
    } catch (error) {
      setIsLoading(false)
      console.error('Error saving explore selection:', error)
      return { success: false, error }
    }
  }
  
  // Function to update an existing explore selection
  const updateExistingSelection = async (
    id: string,
    modelName: string,
    exploreId: string,
    selectionData: any
  ) => {
    setIsLoading(true)
    try {
      // Get current user information
      const currentUser = await extensionSDK.lookerHostData?.getCurrentUser?.() || {}
      const userId = currentUser?.id?.toString() || 'unknown_user'
      
      // Get the original creation time from the existing record
      const existingSelections = await getUserExploreSelections(userId)
      const existingSelection = existingSelections.find(s => s.id === id)
      
      if (!existingSelection) {
        throw new Error(`Selection with id ${id} not found`)
      }
      
      const createdAt = new Date(existingSelection.createdAt).toISOString()
      const now = new Date().toISOString()
      const selectionDataStr = typeof selectionData === 'string' 
        ? selectionData 
        : JSON.stringify(selectionData)
      
      // Use the upsert operation
      await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: {
            model: modelName,
            view: "explore_selection_upsert",
            fields: ["explore_selection_upsert.status"],
            parameters: {
              id: id,
              model_name: modelName,
              explore_id: exploreId,
              user_id: userId,
              selection_data: selectionDataStr,
              created_at: createdAt
            }
          }
        })
      )
      
      // Create the updated selection object
      const selection = {
        id,
        modelName,
        exploreId,
        userId,
        selectionData,
        createdAt: existingSelection.createdAt,
        updatedAt: new Date(now).getTime()
      }
      
      // Update Redux store
      dispatch(updateExploreSelection(selection))
      
      setIsLoading(false)
      return { success: true, selection }
    } catch (error) {
      setIsLoading(false)
      console.error('Error updating explore selection:', error)
      return { success: false, error }
    }
  }
  
  return { 
    isLoading,
    ensureExploreSelectionTable, 
    getUserExploreSelections, 
    saveExploreSelection, 
    updateExistingSelection
  }
}