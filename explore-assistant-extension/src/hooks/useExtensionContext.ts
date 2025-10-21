import { useContext, useEffect, useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { RootState } from '../store'
import { 
  AssistantState, 
  setUserAttributesLoaded
} from '../slices/assistantSlice'

// Debug flag for extension context loading
const CONTEXT_DEBUG = true

export const useExtensionContext = () => {
  const { extensionSDK } = useContext(ExtensionContext)
  const dispatch = useDispatch()
  
  const { userAttributesLoaded } = useSelector(
    (state: RootState) => state.assistant as AssistantState,
  )
  
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadExtensionContext = async () => {
    if (isLoading || userAttributesLoaded) {
      CONTEXT_DEBUG && console.log('Extension context already loaded or loading in progress')
      return
    }

    if (!extensionSDK) {
      CONTEXT_DEBUG && console.log('Cannot load extension context: missing extensionSDK')
      return
    }
    try {
      setIsLoading(true)
      setError(null)
      CONTEXT_DEBUG && console.log('===== Loading Extension Context =====')

      // Get extension context data
      const contextData = await extensionSDK.getContextData()
      CONTEXT_DEBUG && console.log('Extension context data:', contextData)

      // Note: Settings now come from environment variables, not extension context
      CONTEXT_DEBUG && console.log('Extension context loaded successfully (settings now from environment)')
      
      // Mark context as loaded
      dispatch(setUserAttributesLoaded(true))
      
    } catch (error) {
      console.error('Error loading extension context:', error)
      setError(error instanceof Error ? error.message : 'Failed to load extension context')
      // Still mark as loaded to prevent infinite retries
      dispatch(setUserAttributesLoaded(true))
    } finally {
      setIsLoading(false)
    }
  }

  const saveExtensionContext = async (settingsToSave: Record<string, any>) => {
    // Settings are now read-only from environment variables
    CONTEXT_DEBUG && console.log('Settings save requested but ignored (settings now from environment):', settingsToSave)
    return true // Return success to maintain interface compatibility
  }

  // Load extension context on mount
  useEffect(() => {
    if (!userAttributesLoaded && extensionSDK) {
      loadExtensionContext()
    }
  }, [extensionSDK])

  return {
    isLoading,
    error,
    contextLoaded: userAttributesLoaded, // Keep same interface
    loadExtensionContext,
    saveExtensionContext
  }
}
