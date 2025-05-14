import { useContext, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  setExploreGenerationExamples,
  setExploreRefinementExamples,
  setExploreSamples,
  setisBigQueryMetadataLoaded,
  setCurrenExplore,
  AssistantState,
  setBigQueryTestSuccessful
} from '../slices/assistantSlice'

import { ExtensionContext } from '@looker/extension-sdk-react'
import { useErrorBoundary } from 'react-error-boundary'
import { RootState } from '../store'

// Global state to track active fetches and cache results
const globalState = {
  isFetching: false,
  hasLoaded: false,
  cachedResponse: null,
  pendingPromise: null as Promise<any> | null
}

export const useBigQueryExamples = () => {
  const dispatch = useDispatch()
  const { showBoundary } = useErrorBoundary()
  const { isBigQueryMetadataLoaded, settings } = useSelector((state: RootState) => state.assistant as AssistantState)
  
  const { core40SDK } = useContext(ExtensionContext)
  // Get model name from settings instead of parsing from URL context
  const modelName = settings?.bigquery_example_looker_model_name?.value as string || 'explore_assistant'

  // Use a ref to track if examples have loaded in this component instance
  const instanceHasFetched = useRef(false)
  
  const runExampleQuery = async (forceRefresh = false) => {
    // If we already have cached data and we're not forcing a refresh, use it
    if (globalState.cachedResponse && !forceRefresh) {
      console.log('Using cached BigQuery examples data')
      return globalState.cachedResponse
    }
    
    // If a query is currently in progress, return that promise
    if (globalState.isFetching && globalState.pendingPromise) {
      console.log('BigQuery examples query already in progress, joining existing request')
      return globalState.pendingPromise
    }

    console.log('Initiating BigQuery examples query with model name:', modelName)
    // Otherwise, initiate a new query
    globalState.isFetching = true
    
    const newPromise = (async () => {
      try {
        const query = await core40SDK.ok(
          core40SDK.run_inline_query({
            result_format: 'json',
            body: {
              model: modelName, // Use the model name from settings
              view: "explore_assistant_examples",
              fields: [`explore_assistant_examples.explore_id`, `explore_assistant_examples.examples`, `explore_assistant_refinement_examples.examples`, `explore_assistant_samples.samples`],
            }
          })
        )

        if (query === undefined) {
          return []
        }
        
        // Cache the result
        globalState.cachedResponse = query
        globalState.hasLoaded = true
        return query
      } catch (error) {
        if (error.name === 'LookerSDKError' || error.message === 'Model Not Found') {
          console.error('Error running query:', error.message)
          return []
        }
        showBoundary(error)
        throw new Error('error')
      } finally {
        globalState.isFetching = false
        globalState.pendingPromise = null
      }
    })()
    
    globalState.pendingPromise = newPromise
    return newPromise
  }

  const getExamplesAndSamples = async () => {
    // If data is already loaded in Redux, don't fetch again
    if (isBigQueryMetadataLoaded && globalState.hasLoaded) {
      console.log('BigQuery examples data already loaded in Redux')
      return
    }

    return runExampleQuery().then((response) => {
      if(response.length === 0 || !Array.isArray(response)) {
        return
      }
      const generationExamples = {
        examples: {},
        refinement_examples: {},
        samples: {}
      };
      
      response.forEach((row: any) => {
        generationExamples['examples'][row['explore_assistant_examples.explore_id']] = JSON.parse(row['explore_assistant_examples.examples'])
        generationExamples['refinement_examples'][row['explore_assistant_examples.explore_id']] = JSON.parse(row['explore_assistant_refinement_examples.examples'] ?? '[]')
        generationExamples['samples'][row['explore_assistant_examples.explore_id']] = JSON.parse(row['explore_assistant_samples.samples'])
      })
      
      dispatch(setisBigQueryMetadataLoaded(true))
      dispatch(setExploreGenerationExamples(generationExamples['examples']))
      dispatch(setExploreRefinementExamples(generationExamples['refinement_examples']))
      dispatch(setExploreSamples(generationExamples['samples']))
      
      // Get the explore ID from the response
      const exploreKey: string = response[0]['explore_assistant_examples.explore_id']
      
      // Don't use modelName from exploreKey split - keep the one from settings
      // Instead, only extract the exploreId portion
      let exploreId: string
      
      // Check if exploreKey contains a colon (indicating it has model:explore format)
      if (exploreKey.includes(':')) {
        // Just extract the explore ID part after the colon
        exploreId = exploreKey.split(':')[1]
      } else {
        // If there's no colon, use the whole key as the explore ID
        exploreId = exploreKey
      }
      
      // Create a new exploreKey using the model name from settings
      const newExploreKey = `${modelName}:${exploreId}`
      
      console.log(`Setting current explore with model: ${modelName}, explore: ${exploreId}, key: ${newExploreKey}`)
      
      // Validate that both modelName and exploreId are non-empty before setting the current explore
      if (modelName && exploreId) {
        dispatch(setCurrenExplore({
          exploreKey: newExploreKey,
          modelName: modelName, // Always use the model name from settings
          exploreId: exploreId
        }))
      } else {
        console.error('Cannot set current explore: model name or explore ID is missing', { modelName, exploreId })
        showBoundary({
          message: 'Default Looker Model or Explore is blank or unspecified',
          _looker_reported: true
        })
      }
    }).catch((error) => showBoundary(error))
  }

  const testBigQuerySettings = async () => {
    console.log('Testing BigQuery settings with model:', modelName)
    try {
      // For testing, we want a fresh query to ensure settings are working
      const response = await runExampleQuery(true)
      const successful = response.length > 0
      dispatch(setBigQueryTestSuccessful(successful))
      return successful
    } catch (error) {
      dispatch(setBigQueryTestSuccessful(false))
      console.error('Error testing BigQuery settings:', error)
      return false
    }
  }

  // Load examples data on component mount if not already loaded
  useEffect(() => {
    if (instanceHasFetched.current) return
    instanceHasFetched.current = true
    
    // If data is already loaded in Redux, don't fetch again
    if (isBigQueryMetadataLoaded && globalState.hasLoaded) {
      console.log('BigQuery examples data already loaded, skipping fetch')
      return
    }

    dispatch(setisBigQueryMetadataLoaded(false))
    getExamplesAndSamples()
      .then(() => {
        console.log('BigQuery examples data loaded successfully')
        dispatch(setisBigQueryMetadataLoaded(true))
      })
      .catch((error) => {
        console.error('Failed to load BigQuery examples data:', error)
        showBoundary(error)
        dispatch(setisBigQueryMetadataLoaded(false))
      })
  }, [])

  return {
    testBigQuerySettings,
    getExamplesAndSamples,
    // Add a function to invalidate cache if needed
    invalidateCache: () => {
      globalState.cachedResponse = null
      globalState.hasLoaded = false
      return getExamplesAndSamples()
    }
  }
}