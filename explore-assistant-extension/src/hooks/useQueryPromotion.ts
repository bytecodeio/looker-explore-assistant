import { useCallback, useContext } from 'react'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { appConfig } from '../config'

interface PromotionResult {
  new_query_id: string
  source_query_id: string
  source_table: string
  target_table: string
  promoted_by: string
}

interface QueriesResult {
  queries: any[]
  total: number
}

interface HistoryResult {
  history: any[]
  total: number
}

export const useQueryPromotion = () => {
  const { extensionSDK } = useContext(ExtensionContext)

  // Cloud Run service settings from configuration
  const CLOUD_RUN_URL = appConfig.cloudRunServiceUrl
  const identityToken = '' // TODO: Implement proper identity token retrieval

  const getQueriesForPromotion = useCallback(async (
    tableName: 'bronze' | 'silver',
    limit: number = 50,
    offset: number = 0
  ): Promise<QueriesResult> => {
    if (!CLOUD_RUN_URL) {
      throw new Error('Cloud Run URL not configured')
    }
    
    if (!identityToken) {
      throw new Error('Identity token not available')
    }

    try {
      console.log(`Getting queries for promotion from ${tableName} table...`)
      
      // Use REST API endpoint: GET /api/v1/admin/queries/<table_name>
      const response = await extensionSDK.fetchProxy(`${CLOUD_RUN_URL}/api/v1/admin/queries/${tableName}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${identityToken}`,
        }
      })

      if (!response.ok) {
        const errorText = response.body?.error || `HTTP ${response.status}`
        throw new Error(errorText)
      }

      const result = response.body
      
      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to get queries')
      }
      
      // Apply pagination manually since the API doesn't support it yet
      const allQueries = result.data || []
      const startIndex = offset
      const endIndex = startIndex + limit
      const paginatedQueries = allQueries.slice(startIndex, endIndex)
      
      return {
        queries: paginatedQueries,
        total: allQueries.length
      }
    } catch (error) {
      console.error(`Error fetching ${tableName} queries:`, error)
      throw error
    }
  }, [CLOUD_RUN_URL, identityToken, extensionSDK])

  const promoteQuery = useCallback(async (
    queryId: string,
    sourceTable: string,
    targetTable: string = 'golden',
    reason: string = ''
  ): Promise<PromotionResult> => {
    if (!CLOUD_RUN_URL) {
      throw new Error('Cloud Run URL not configured')
    }
    
    if (!identityToken) {
      throw new Error('Identity token not available')
    }

    try {
      console.log('Promoting query with REST API:', { queryId, sourceTable, targetTable, reason })
      
      // Use REST API endpoint: POST /api/v1/admin/promote
      const response = await extensionSDK.fetchProxy(`${CLOUD_RUN_URL}/api/v1/admin/promote`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${identityToken}`,
        },
        body: JSON.stringify({
          query_id: queryId,
          target_rank: targetTable === 'golden' ? 'GOLD' : targetTable.toUpperCase(),
          promoted_by: 'user', // You might want to get actual user info
          promotion_reason: reason || undefined
        })
      })

      if (!response.ok) {
        const errorText = response.body?.error || `HTTP ${response.status}`
        throw new Error(errorText)
      }

      const result = response.body

      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to promote query')
      }

      console.log('Query promoted successfully:', result)
      
      return {
        new_query_id: result.data?.new_query_id || result.data?.query_id || queryId,
        source_query_id: queryId,
        source_table: sourceTable,
        target_table: targetTable === 'golden' ? 'gold' : targetTable, // Olympic system uses 'gold' instead of 'golden'
        promoted_by: result.data?.promoted_by || 'user'
      }
    } catch (error) {
      console.error('Error promoting query:', error)
      throw error
    }
  }, [CLOUD_RUN_URL, identityToken, extensionSDK])

  const getPromotionHistory = useCallback(async (
    limit: number = 50,
    offset: number = 0
  ): Promise<HistoryResult> => {
    if (!CLOUD_RUN_URL) {
      throw new Error('Cloud Run URL not configured')
    }
    
    if (!identityToken) {
      throw new Error('Identity token not available')
    }

    try {
      console.log('Getting promotion history...')
      
      // Note: There's no specific promotion history endpoint in the backend yet,
      // so we'll use the stats endpoint which provides overview data
      // Use REST API endpoint: GET /api/v1/admin/stats
      const response = await extensionSDK.fetchProxy(`${CLOUD_RUN_URL}/api/v1/admin/stats`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${identityToken}`,
        }
      })

      if (!response.ok) {
        const errorText = response.body?.error || `HTTP ${response.status}`
        throw new Error(errorText)
      }

      const result = response.body
      
      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to get promotion history')
      }
      
      // Transform stats data into history format
      // This is a placeholder implementation since the backend doesn't have detailed history yet
      const statsData = result.data || {}
      const mockHistory = [
        {
          id: 'stats-summary',
          action: 'query_stats',
          timestamp: new Date().toISOString(),
          details: statsData,
          promoted_by: 'system'
        }
      ]
      
      // Apply pagination
      const startIndex = offset
      const endIndex = startIndex + limit
      const paginatedHistory = mockHistory.slice(startIndex, endIndex)
      
      return {
        history: paginatedHistory,
        total: mockHistory.length
      }
    } catch (error) {
      console.error('Error fetching promotion history:', error)
      throw error
    }
  }, [CLOUD_RUN_URL, identityToken, extensionSDK])

  return {
    getQueriesForPromotion,
    promoteQuery,
    getPromotionHistory
  }
}
