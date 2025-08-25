import { useContext, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  AssistantState,
  SemanticModel,
  setIsSemanticModelLoaded,
  setSemanticModels,
} from '../slices/assistantSlice'
import { RootState } from '../store'
import { ExtensionContext } from '@looker/extension-sdk-react'

export const useLookerFields = () => {
  const {
    examples: { exploreSamples },
    isSemanticModelLoaded,
  } = useSelector((state: RootState) => state.assistant as AssistantState)

  const supportedExplores = Object.keys(exploreSamples)

  const dispatch = useDispatch()

  const { core40SDK } = useContext(ExtensionContext)

  // Create a ref to track if the hook has already been called
  const hasFetched = useRef(false)

  // Load LookML metadata and provide completion status
  useEffect(() => {
    // if the hook has already been called, return
    if (hasFetched.current) return

    // if there are no supported explores or the semantic model is already loaded, return
    if (supportedExplores.length === 0 || isSemanticModelLoaded) {
      return
    }
    
    // mark
    hasFetched.current = true

    const fetchSemanticModel = async (
      modelName: string,
      exploreId: string,
      exploreKey: string,
    ): Promise<SemanticModel | undefined> => {
      if (!modelName || !exploreId) {
        console.warn('Default Looker Model or Explore is blank or unspecified', { modelName, exploreId })
        return undefined
      }

      try {
        const response = await core40SDK.ok(
          core40SDK.lookml_model_explore({
            lookml_model_name: modelName,
            explore_name: exploreId,
            fields: 'fields, description',
          }),
        )

        console.log(`Fetched semantic model for ${modelName}:${exploreId}`, response)
        const { fields, description } = response

        if (!fields || !fields.dimensions || !fields.measures) {
          return undefined
        }

        const dimensions = fields.dimensions
          .filter(({ hidden }: any) => !hidden)
          .map(({ name, type, label, description, tags }: any) => ({
            name,
            type,
            label,
            description,
            tags,
          }))

        const measures = fields.measures
          .filter(({ hidden }: any) => !hidden)
          .map(({ name, type, label, description, tags }: any) => ({
            name,
            type,
            label,
            description,
            tags,
          }))

        return {
          exploreId,
          modelName,
          exploreKey,
          dimensions,
          measures,
          description: description || '',
        }
      } catch (error: any) {
        // Check if it's a 404 or model not found error
        if (error.message?.includes('404') || error.message?.includes('Not Found') || 
            error.message?.includes('Model Not Found') || error.message?.includes('Explore Not Found')) {
          console.warn(`Model/Explore not available: ${modelName}:${exploreId} - ${error.message}`)
          return undefined // Return undefined instead of crashing
        }
        
        // For other errors, still log but don't crash the app
        console.error(`Error fetching semantic model for ${modelName}:${exploreId}:`, error)
        return undefined
      }
    }

    const loadSemanticModels = async () => {
      console.log('Loading semantic models...')
      try {
        const fetchPromises = supportedExplores.map((exploreKey) => {
          const [modelName, exploreId] = exploreKey.split(':')
          return fetchSemanticModel(modelName, exploreId, exploreKey).then(
            (model) => ({ exploreKey, model })
          )
        })

        // Use manual promise handling for better compatibility
        const results = await Promise.all(
          fetchPromises.map(async (promise) => {
            try {
              const result = await promise
              return { status: 'fulfilled' as const, value: result }
            } catch (error) {
              return { status: 'rejected' as const, reason: error }
            }
          })
        )
        const semanticModels: { [explore: string]: SemanticModel } = {}
        const failedModels: string[] = []

        results.forEach((result: any, index: number) => {
          if (result.status === 'fulfilled' && result.value.model) {
            const { exploreKey, model } = result.value
            semanticModels[exploreKey] = model
          } else {
            const exploreKey = supportedExplores[index]
            failedModels.push(exploreKey)
            if (result.status === 'rejected') {
              console.warn(`Failed to load model: ${exploreKey}`, result.reason)
            } else {
              console.warn(`Model returned no data: ${exploreKey}`)
            }
          }
        })
        const loadedCount = Object.keys(semanticModels).length
        const totalCount = supportedExplores.length
        
        console.log(`Loaded semantic models: ${loadedCount}/${totalCount}`, semanticModels)
        if (failedModels.length > 0) {
          console.warn(`Failed to load ${failedModels.length} models:`, failedModels)
        }
        
        dispatch(setSemanticModels(semanticModels))
        // Mark as loaded even if some models failed - we'll work with what we have
        dispatch(setIsSemanticModelLoaded(true))
      } catch (error) {
        console.error('Critical error loading semantic models:', error)
        // Don't crash the app - set loaded to true with empty models
        dispatch(setSemanticModels({}))
        dispatch(setIsSemanticModelLoaded(true))
      }
    }

    loadSemanticModels()
  }, [supportedExplores])
}
