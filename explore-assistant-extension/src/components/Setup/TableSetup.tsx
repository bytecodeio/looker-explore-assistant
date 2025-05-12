// src/components/Setup/TableSetup.tsx
import React, { useState, useEffect } from 'react'
import { useSetupHelper } from '../../utils/SetupHelper'
import { Button, MessageBar, Spinner } from '@looker/components'

export const TableSetup: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [tableExists, setTableExists] = useState(false)
  const [error, setError] = useState('')
  const { createExploreSelectionTable, checkExploreSelectionTable } = useSetupHelper()
  
  useEffect(() => {
    checkTableStatus()
  }, [])
  
  const checkTableStatus = async () => {
    setLoading(true)
    try {
      const { exists, error } = await checkExploreSelectionTable('your_connection_name')
      setTableExists(exists)
      if (error) {
        setError('Error checking table status')
      }
    } catch (err) {
      setError('An error occurred while checking table status')
    } finally {
      setLoading(false)
    }
  }
  
  const handleCreateTable = async () => {
    setLoading(true)
    try {
      const { success, error } = await createExploreSelectionTable('your_connection_name')
      if (success) {
        setTableExists(true)
      } else {
        setError(error || 'Failed to create table')
      }
    } catch (err) {
      setError('An error occurred while creating the table')
    } finally {
      setLoading(false)
    }
  }
  
  if (loading) {
    return <Spinner />
  }
  
  return (
    <div>
      <h2>Explore Selection Table Setup</h2>
      
      {error && (
        <MessageBar intent="critical">
          {error}
        </MessageBar>
      )}
      
      {tableExists ? (
        <MessageBar intent="positive">
          The explore_selection table exists and is ready to use.
        </MessageBar>
      ) : (
        <>
          <MessageBar intent="warn">
            The explore_selection table doesn't exist yet.
          </MessageBar>
          <Button onClick={handleCreateTable}>
            Create Table
          </Button>
        </>
      )}
    </div>
  )
}