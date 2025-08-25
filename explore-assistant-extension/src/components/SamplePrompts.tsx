import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  AssistantState,
  resetChat,
  setIsChatMode,
  setQuery,
  ensureValidExploreContext,
} from '../slices/assistantSlice'
import { RootState } from '../store'

const SamplePrompts = () => {
  const dispatch = useDispatch()
  const {
    currentExplore: { modelName, exploreId, exploreKey },
    examples: { exploreSamples },
    selectedArea,
    selectedExplores,
    availableAreas,
    semanticModels,
  } = useSelector((state: RootState) => state.assistant as AssistantState)

  // Ensure we have a valid explore context when component mounts
  useEffect(() => {
    if (!modelName || !exploreId || !exploreKey) {
      dispatch(ensureValidExploreContext())
    }
  }, [modelName, exploreId, exploreKey, dispatch])

  // Get available explores (those with loaded semantic models)
  const getAvailableSelectedExplores = () => {
    if (!selectedExplores) return []
    return selectedExplores.filter(exploreKey => {
      // Only include explores that have successfully loaded semantic models and have samples
      return semanticModels[exploreKey] && exploreSamples[exploreKey]
    })
  }
  
  // Get unavailable explores for warning display
  const getUnavailableSelectedExplores = () => {
    if (!selectedExplores) return []
    return selectedExplores.filter(exploreKey => {
      // Include explores that don't have semantic models or samples
      return !semanticModels[exploreKey] || !exploreSamples[exploreKey]
    })
  }

  // Check if user has selected an area and one or more explores
  if (!selectedArea || !selectedExplores || selectedExplores.length === 0) {
    return (
      <div className="text-gray-500 p-4 text-center">
        <p>Please select a business area and one or more data models to see sample prompts</p>
      </div>
    )
  }
  
  const availableExplores = getAvailableSelectedExplores()
  const unavailableExplores = getUnavailableSelectedExplores()
  
  // Show warning if some selected explores are not available
  const hasUnavailableExplores = unavailableExplores.length > 0

  // Get all sample prompts for the available selected explores
  const getSelectedExploresSamples = () => {
    const allSamples: any[] = []
    const availableExplores = getAvailableSelectedExplores()
    
    availableExplores.forEach(exploreKey => {
      const samples = exploreSamples[exploreKey]
      if (samples && Array.isArray(samples)) {
        // Add explore context to each sample for identification
        const samplesWithContext = samples.map(sample => ({
          ...sample,
          sourceExplore: exploreKey,
          sourceExploreName: getExploreDisplayName(exploreKey)
        }))
        allSamples.push(...samplesWithContext)
      }
    })
    
    return allSamples
  }

  // Helper to get display name for an explore
  const getExploreDisplayName = (exploreKey: string) => {
    if (!selectedArea) return exploreKey
    
    const area = availableAreas.find(a => a.area === selectedArea)
    const details = area?.explore_details?.[exploreKey]
    
    if (details?.display_name) {
      return details.display_name
    }
    
    // Fallback: create display name from explore key
    const fallbackDisplayName = exploreKey.split(':')[1]?.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) || exploreKey
    return fallbackDisplayName
  }

  const allSelectedSamples = getSelectedExploresSamples()

  const handleSubmit = (prompt: string) => {
    // Don't reset chat completely - preserve the current explore context
    dispatch(setQuery(prompt))
    dispatch(setIsChatMode(true))
  }

  // Helper function to extract prompt text from any format
  const getPromptText = (item: any): string => {
    if (typeof item === 'string') {
      return item
    }
    if (typeof item === 'object' && item !== null) {
      // Try common property names for prompt text
      return item.prompt || item.text || item.question || item.query || item.example || JSON.stringify(item)
    }
    // Fallback to string representation
    return String(item)
  }

  // Helper function to extract category from any format, including explore context
  const getCategory = (item: any): string => {
    if (typeof item === 'object' && item !== null) {
      // If we have source explore info, use it for better categorization
      if (item.sourceExploreName) {
        const baseCategory = item.category || item.type || item.tag || 'Sample'
        return `${baseCategory} (${item.sourceExploreName})`
      }
      return item.category || item.type || item.tag || 'Sample'
    }
    return 'Sample'
  }

  // Filter out invalid samples and ensure we have valid prompt text
  const validSamples = allSelectedSamples?.filter(item => {
    const promptText = getPromptText(item)
    return promptText && promptText.trim().length > 0
  }) || []

  if (validSamples.length === 0) {
    // Log unavailable models to console instead of showing visible warnings
    if (hasUnavailableExplores) {
      console.warn('Sample prompts not available for:', unavailableExplores.map(key => key.split(':')[1]).join(', '))
      console.warn('These data models may still be loading or unavailable.')
    }
    
    return (
      <div className="text-2xl text-gray-400">
        <p>No sample prompts available for the selected data models</p>
      </div>
    )
  }

  // Log model availability info to console
  if (hasUnavailableExplores) {
    console.warn('Some selected data models are not yet available:', unavailableExplores.map(key => key.split(':')[1]).join(', '))
    console.log('Showing prompts for available models only.')
  }
  
  console.log(`Sample prompts: ${availableExplores.length} of ${selectedExplores.length} data models available for area: ${selectedArea}`)

  return (
    <div className="flex flex-col max-w-5xl">
      <div className="mb-4  ml-2 ">
        <p className="text-l text-gray-400">
          Sample prompts for <span className="font-semibold">{selectedArea}</span> area
          {selectedExplores.length > 1 ? ` (${selectedExplores.length} data models selected)` : ''}
        </p>
      </div>
      <div className="flex flex-wrap">
        {validSamples.map((item, index: number) => {
          const promptText = getPromptText(item)
          const category = getCategory(item)
          
          return (
            <div
              className="flex flex-col w-56 min-h-44 bg-gray-200/50 hover:bg-gray-200 rounded-lg cursor-pointer text-sm p-4 m-2"
              key={index}
              onClick={() => {
                handleSubmit(promptText)
              }}
            >
              <div className="flex-grow font-light line-clamp-5">{promptText}</div>
              <div className="mt-2 font-semibold justify-end">{category}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default SamplePrompts
