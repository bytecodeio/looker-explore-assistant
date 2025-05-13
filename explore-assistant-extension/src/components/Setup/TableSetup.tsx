// src/components/Setup/TableSetup.tsx
import React, { useState, useEffect } from 'react'
import { useSetupHelper } from '../../utils/SetupHelper'
import { Button, MessageBar, Space, Spinner, SpaceVertical } from '@looker/components'

interface TableSetupProps {
  onInitialized?: () => void;
}

export const TableSetup: React.FC<TableSetupProps> = ({ onInitialized }) => {
  const [loading, setLoading] = useState(true)
  const [tableStatus, setTableStatus] = useState<{
    exploreSelection: { exists: boolean; rowCount: number; message: string } | null;
    explores: { exists: boolean; rowCount: number; message: string } | null;
  }>({
    exploreSelection: null,
    explores: null
  })
  const [error, setError] = useState('')
  
  const { 
    initExploreSelectionTable, 
    initExploresTable, 
    populateExploresTable,
    checkTableRowCount
  } = useSetupHelper()
  
  // Check both tables status when component loads
  useEffect(() => {
    checkTablesStatus()
  }, [])
  
  const checkTablesStatus = async () => {
    setLoading(true)
    setError('')
    
    try {
      const exploreSelectionStatus = await checkTableRowCount('explore_selection')
      const exploresStatus = await checkTableRowCount('explores')
      
      setTableStatus({
        exploreSelection: exploreSelectionStatus,
        explores: exploresStatus
      })
    } catch (err) {
      setError('An error occurred while checking tables status')
    } finally {
      setLoading(false)
    }
  }
  
  const handleCreateTables = async () => {
    setLoading(true)
    setError('')
    
    try {
      // Initialize explore selection table
      const exploreSelectionResult = await initExploreSelectionTable()
      if (!exploreSelectionResult.success) {
        throw new Error(exploreSelectionResult.message)
      }
      
      // Initialize explores table
      const exploresResult = await initExploresTable()
      if (!exploresResult.success) {
        throw new Error(exploresResult.message)
      }
      
      // Check status after initialization
      await checkTablesStatus()
      
      // Call the onInitialized callback if provided
      if (onInitialized) {
        onInitialized()
      }
    } catch (err) {
      setError(`An error occurred while creating tables: ${err.message || err}`)
      setLoading(false)
    }
  }
  
  const handlePopulateTables = async () => {
    setLoading(true)
    setError('')
    
    try {
      // Populate explores table with Looker data
      const populateResult = await populateExploresTable()
      if (!populateResult.success) {
        throw new Error(populateResult.message)
      }
      
      // Check status after population
      await checkTablesStatus()
      
      // Call the onInitialized callback if provided
      if (onInitialized) {
        onInitialized()
      }
    } catch (err) {
      setError(`An error occurred while populating explores: ${err.message || err}`)
      setLoading(false)
    }
  }
  
  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <SpaceVertical>
          <Spinner size="large" />
          <div>Checking tables status...</div>
        </SpaceVertical>
      </div>
    )
  }
  
  const tablesExist = tableStatus.exploreSelection?.exists && tableStatus.explores?.exists
  const tablesPopulated = (tableStatus.explores?.rowCount || 0) > 0
  
  return (
    <div style={{ padding: '20px' }}>
      <h2>Explore Selection Tables Setup</h2>
      
      {error && (
        <MessageBar intent="critical" visible>
          {error}
        </MessageBar>
      )}
      
      <SpaceVertical>
        <div>
          <h3>Tables Status</h3>
          
          <div>Explore Selection Table: {' '}
            {tableStatus.exploreSelection?.exists ? (
              <span style={{ color: 'green', fontWeight: 'bold' }}>
                Exists ({tableStatus.exploreSelection.rowCount} rows)
              </span>
            ) : (
              <span style={{ color: 'red', fontWeight: 'bold' }}>
                Not found
              </span>
            )}
          </div>
          
          <div>Explores Metadata Table: {' '}
            {tableStatus.explores?.exists ? (
              <span style={{ color: 'green', fontWeight: 'bold' }}>
                Exists ({tableStatus.explores.rowCount} rows)
              </span>
            ) : (
              <span style={{ color: 'red', fontWeight: 'bold' }}>
                Not found
              </span>
            )}
          </div>
        </div>
        
        <Space>
          <Button 
            onClick={handleCreateTables} 
            disabled={loading}
            color={tablesExist ? "neutral" : "key"}
          >
            {tablesExist ? "Recreate Tables" : "Create Tables"}
          </Button>
          
          <Button 
            onClick={handlePopulateTables} 
            disabled={loading || !tablesExist}
            color={tablesPopulated ? "neutral" : "key"}
          >
            {tablesPopulated ? "Repopulate Tables" : "Populate Tables"}
          </Button>
          
          <Button 
            onClick={checkTablesStatus} 
            disabled={loading}
            color="neutral"
          >
            Refresh Status
          </Button>
        </Space>
        
        {!tablesExist && (
          <MessageBar intent="warning" visible>
            Tables need to be created before they can be populated with data.
          </MessageBar>
        )}
        
        {tablesExist && !tablesPopulated && (
          <MessageBar intent="warning" visible>
            Tables exist but are not populated with data.
          </MessageBar>
        )}
        
        {tablesExist && tablesPopulated && (
          <MessageBar intent="positive" visible>
            Tables are properly set up and populated with data.
          </MessageBar>
        )}
      </SpaceVertical>
    </div>
  )
}