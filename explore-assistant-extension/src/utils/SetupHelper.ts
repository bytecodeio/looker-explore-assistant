// src/utils/SetupHelper.ts
import { useContext } from 'react'
import { ExtensionContext } from '@looker/extension-sdk-react'

export const useSetupHelper = () => {
  const { core40SDK } = useContext(ExtensionContext)
  
  const createExploreSelectionTable = async (connectionName: string) => {
    try {
      // This assumes you have permissions to execute DDL statements
      // In practice, you might want to have this as part of your deployment process
      const createTableSQL = `
        CREATE TABLE IF NOT EXISTS explore_selection (
          id STRING NOT NULL,
          model_name STRING NOT NULL,
          explore_id STRING NOT NULL,
          user_id STRING NOT NULL,
          selection_data STRING,
          created_at TIMESTAMP NOT NULL,
          updated_at TIMESTAMP NOT NULL,
          PRIMARY KEY(id)
        )
      `
      
      // Execute the DDL through a SQL runner query
      await core40SDK.ok(
        core40SDK.run_sql_query({
          connection_name: connectionName,
          sql: createTableSQL,
          result_format: 'json'
        })
      )
      
      return { success: true }
    } catch (error) {
      console.error('Error creating explore selection table:', error)
      return { success: false, error }
    }
  }
  
  // Check if the explore selection table exists
  const checkExploreSelectionTable = async (connectionName: string) => {
    try {
      const checkTableSQL = `
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name = 'explore_selection'
      `
      
      const response = await core40SDK.ok(
        core40SDK.run_sql_query({
          connection_name: connectionName,
          sql: checkTableSQL,
          result_format: 'json'
        })
      )
      
      return { exists: response && response.length > 0 }
    } catch (error) {
      console.error('Error checking explore selection table:', error)
      return { exists: false, error }
    }
  }
  
  return {
    createExploreSelectionTable,
    checkExploreSelectionTable
  }
}