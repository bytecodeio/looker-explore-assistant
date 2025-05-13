import React, { useState, useEffect } from 'react'
import { useExploreSelection } from '../../hooks/useExploreSelection'
import { useExploreHelper } from '../../hooks/useExploreHelper'
import { Box, MessageBar, Spinner, SpaceVertical } from '@looker/components'

interface TableInitializerProps {
  onInitialized: () => void
}

export const TableInitializer: React.FC<TableInitializerProps> = ({ onInitialized }) => {
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<{
    exploreSelection: boolean
    explores: boolean
    message: string
    error?: string
  }>({
    exploreSelection: false,
    explores: false,
    message: 'Initializing tables...'
  })
  
  const { ensureExploreSelectionTable } = useExploreSelection()
  const { populateExploresTable } = useExploreHelper()
  
  useEffect(() => {
    async function initializeTables() {
      setLoading(true)
      
      try {
        // First ensure the explore selection table exists
        const selectionResult = await ensureExploreSelectionTable()
        setStatus(prev => ({
          ...prev,
          exploreSelection: selectionResult.success,
          message: selectionResult.success 
            ? 'Explore selection table created successfully'
            : 'Failed to create explore selection table'
        }))
        
        if (!selectionResult.success) {
          setLoading(false)
          return
        }
        
        // Then ensure the explores table exists and is populated
        const exploresResult = await populateExploresTable()
        setStatus(prev => ({
          ...prev,
          explores: exploresResult,
          message: exploresResult 
            ? 'Explores table populated successfully'
            : 'Failed to populate explores table'
        }))
        
        if (selectionResult.success && exploresResult) {
          // If both operations succeeded, call the onInitialized callback
          onInitialized()
        }
      } catch (error) {
        setStatus(prev => ({
          ...prev,
          message: 'An error occurred during initialization',
          error: error.toString()
        }))
      } finally {
        setLoading(false)
      }
    }
    
    initializeTables()
  }, [])
  
  if (loading) {
    return (
      <Box p="large" display="flex" flexDirection="column" alignItems="center">
        <SpaceVertical>
          <Spinner size={40} />
          <div>Initializing tables...</div>
        </SpaceVertical>
      </Box>
    )
  }
  
  return (
    <Box p="large">
      <SpaceVertical>
        <MessageBar 
          intent={status.exploreSelection ? 'positive' : 'critical'}
          visible={true}
        >
          {status.exploreSelection 
            ? 'Explore selection table initialized successfully'
            : 'Failed to initialize explore selection table'}
        </MessageBar>
        
        <MessageBar 
          intent={status.explores ? 'positive' : 'critical'}
          visible={true}
        >
          {status.explores 
            ? 'Explores table populated successfully'
            : 'Failed to populate explores table'}
        </MessageBar>
        
        {status.error && (
          <MessageBar intent="critical" visible={true}>
            Error: {status.error}
          </MessageBar>
        )}
      </SpaceVertical>
    </Box>
  )
}