import { useCallback, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { 
  AssistantState, 
  addMessage, 
  setCurrenExplore,
  updateCurrentThread 
} from '../slices/assistantSlice'
import { v4 as uuidv4 } from 'uuid'
import useSendVertexMessage from './useSendVertexMessage'

/**
 * Hook to handle explore selection based on user conversation
 */
export const useConversationExplore = () => {
  const dispatch = useDispatch()
  const [isSelectingExplore, setIsSelectingExplore] = useState(false)
  const { sendMessage } = useSendVertexMessage()

  const { 
    examples, 
    semanticModels,
    currentExplore
  } = useSelector((state: RootState) => state.assistant as AssistantState)
  
  /**
   * Uses AI to find the best explore for a user query and selects it
   * 
   * @param query The user's query to analyze
   * @returns Promise that resolves to true if an explore was selected, false otherwise
   */
  const findAndSelectExplore = useCallback(async (query: string): Promise<boolean> => {
    if (isSelectingExplore) return false
    setIsSelectingExplore(true)

    try {
      // Build a list of available explores with their descriptions
      const availableExplores = Object.keys(examples.exploreSamples).map((key) => {
        const [modelName, exploreId] = key.split(':')
        
        // Get additional info from semantic models if available
        const semanticModel = semanticModels[key]
        const description = semanticModel ? 
          `Contains dimensions: ${semanticModel.dimensions.slice(0, 5).map(d => d.name).join(', ')}... and measures: ${semanticModel.measures.slice(0, 5).map(m => m.name).join(', ')}...` : 
          `A data model for ${exploreId.replace(/_/g, ' ')}`
        
        return {
          exploreKey: key,
          modelName,
          exploreId,
          description
        }
      })

      if (availableExplores.length === 0) {
        // No explores available, add system message and return false
        dispatch(
          addMessage({
            uuid: uuidv4(),
            message: "I couldn't find any data explores to search. Please check your configuration.",
            actor: 'system',
            createdAt: Date.now(),
            type: 'text',
          }),
        )
        setIsSelectingExplore(false)
        return false
      }
      
      // Use the AI to select the best explore
      const prompt = `
        Given a user's data question and a list of available Looker explores, 
        determine which explore would be most appropriate for answering the question.
        
        User question: ${query}
        
        Available Explores:
        ${availableExplores.map(explore => 
          `- Model: ${explore.modelName}, Explore: ${explore.exploreId}, Description: ${explore.description}`
        ).join('\n')}
        
        Return your answer as a JSON object with the following structure:
        {
            "selected_explore": {
                "model_name": "name_of_the_model",
                "name": "name_of_the_explore"
            },
            "explanation": "Brief explanation of why this explore was selected"
        }
      `
      
      const response = await sendMessage(prompt, {
        temperature: 0.2,
        maxOutputTokens: 1000
      })
      
      // Extract JSON from the response
      let result
      try {
        // Find JSON object in the response - it might be wrapped in code blocks
        const jsonMatch = response.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/) || 
                          response.match(/(\{[\s\S]*?\})/)
        
        if (jsonMatch && jsonMatch[1]) {
          result = JSON.parse(jsonMatch[1])
        } else {
          throw new Error('Could not extract JSON from response')
        }
      } catch (error) {
        console.error('Error parsing explore selection response:', error)
        console.log('Raw response:', response)
        
        // If parsing fails and we have explores, use the first one as fallback
        if (availableExplores.length > 0) {
          result = {
            selected_explore: {
              model_name: availableExplores[0].modelName,
              name: availableExplores[0].exploreId
            },
            explanation: "I'm using a default explore because I couldn't determine the best one."
          }
        } else {
          setIsSelectingExplore(false)
          return false
        }
      }
      
      if (!result || !result.selected_explore) {
        setIsSelectingExplore(false)
        return false
      }
      
      const selected = result.selected_explore
      const exploreKey = `${selected.model_name}:${selected.name}`
      
      // Verify the selected explore exists
      const selectedExplore = availableExplores.find(e => 
        e.modelName === selected.model_name && e.exploreId === selected.name
      )
      
      if (!selectedExplore) {
        // If the selected explore doesn't exist, use the first available one
        if (availableExplores.length > 0) {
          const fallbackExplore = availableExplores[0]
          dispatch(setCurrenExplore({
            modelName: fallbackExplore.modelName,
            exploreId: fallbackExplore.exploreId,
            exploreKey: fallbackExplore.exploreKey
          }))
          
          // Update thread with explore selection
          dispatch(updateCurrentThread({
            modelName: fallbackExplore.modelName,
            exploreId: fallbackExplore.exploreId
          }))
          
          // Add a message about the selection
          dispatch(
            addMessage({
              uuid: uuidv4(),
              message: `I'll use the ${fallbackExplore.exploreId.replace(/_/g, ' ')} data to answer your question.`,
              actor: 'system',
              createdAt: Date.now(),
              type: 'text',
            }),
          )
        } else {
          setIsSelectingExplore(false)
          return false
        }
      } else {
        // Set the selected explore
        dispatch(setCurrenExplore({
          modelName: selected.model_name,
          exploreId: selected.name,
          exploreKey: exploreKey
        }))
        
        // Update thread with explore selection
        dispatch(updateCurrentThread({
          modelName: selected.model_name,
          exploreId: selected.name
        }))
        
        // Add a message about the selection with the explanation
        dispatch(
          addMessage({
            uuid: uuidv4(),
            message: `I'll use the ${selected.name.replace(/_/g, ' ')} data to answer your question. ${result.explanation || ''}`,
            actor: 'system',
            createdAt: Date.now(),
            type: 'text',
          }),
        )
      }
      
      setIsSelectingExplore(false)
      return true
    } catch (error) {
      console.error('Error selecting explore:', error)
      
      // Add error message
      dispatch(
        addMessage({
          uuid: uuidv4(),
          message: "I had trouble selecting the right data source. Let's continue with your question anyway.",
          actor: 'system',
          createdAt: Date.now(),
          type: 'text',
        }),
      )
      
      setIsSelectingExplore(false)
      return false
    }
  }, [dispatch, examples.exploreSamples, semanticModels, sendMessage, isSelectingExplore])

  return {
    findAndSelectExplore,
    isSelectingExplore
  }
}

export default useConversationExplore