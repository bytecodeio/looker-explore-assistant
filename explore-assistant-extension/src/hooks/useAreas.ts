import { useContext, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { useErrorBoundary } from 'react-error-boundary'
import { RootState } from '../store'
import {
  setAvailableAreas,
  setIsAreasLoaded,
  AssistantState,
  Area
} from '../slices/assistantSlice'

export const useAreas = () => {
  const dispatch = useDispatch()
  const { showBoundary } = useErrorBoundary()
  const { isAreasLoaded, settings } = useSelector((state: RootState) => state.assistant as AssistantState)
  
  const { lookerHostData } = useContext(ExtensionContext)

  const runAreasQuery = async () => {
    try {
      // Get Cloud Run settings
      const CLOUD_RUN_URL = settings?.cloud_run_service_url?.value as string || ''
      const identityToken = settings?.identity_token?.value as string || ''
      
      if (!CLOUD_RUN_URL) {
        console.error('Cloud Run URL not configured')
        return []
      }
      
      if (!identityToken) {
        console.error('Identity token not available')
        return []
      }

      const response = await fetch(`${CLOUD_RUN_URL}/api/v1/areas`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${identityToken}`,
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      
      if (!result.success || !result.data) {
        console.error('Areas API returned unsuccessful response:', result)
        return []
      }
      
      return result.data
    } catch (error: any) {
      console.error('Error fetching areas from backend:', error.message)
      return []
    }
  }

  const getAreas = async () => {
    try {
      const response = await runAreasQuery()
      
      // Better check for empty responses
      if (!response || !Array.isArray(response) || response.length === 0) {
        dispatch(setIsAreasLoaded(false))
        return
      }
      
      // Group explore_keys by area and collect descriptions
      const areasMap: Record<string, { explore_keys: string[], explore_details: Record<string, { description: string, display_name: string }> }> = {}
      
      response.forEach((row: any) => {
        try {
          const area = row.area
          const exploreKey = row.explore_key
          const description = row.description || ''
          
          if (!area || !exploreKey) {
            console.error('Missing area or explore_key in response row', row)
            return
          }
          
          if (!areasMap[area]) {
            areasMap[area] = {
              explore_keys: [],
              explore_details: {}
            }
          }
          
          // Add explore_key if not already present
          if (!areasMap[area].explore_keys.includes(exploreKey)) {
            areasMap[area].explore_keys.push(exploreKey)
          }
          
          // Add explore details with description
          areasMap[area].explore_details[exploreKey] = {
            description: description,
            display_name: exploreKey.split(':')[1]?.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) || exploreKey
          }
        } catch (err) {
          console.error('Error processing areas row:', err, row)
        }
      })
      
      // Convert to Area array
      const areas: Area[] = Object.entries(areasMap).map(([area, data]) => ({
        area,
        explore_keys: data.explore_keys,
        explore_details: data.explore_details
      }))
      
      console.log('Processed areas:', areas)
      
      // Set the data in Redux
      dispatch(setAvailableAreas(areas))
      dispatch(setIsAreasLoaded(true))
      
    } catch (error) {
      console.error('Error in getAreas:', error)
      dispatch(setIsAreasLoaded(false))
      showBoundary(error)
    }
  }

  // Create refs to track state between renders
  const hasFetched = useRef(false)
  const isFetching = useRef(false)

  // Fetch areas on component mount
  useEffect(() => {
    // Synchronously block duplicate fetches at the very top
    if (isFetching.current) {
      console.log('Areas fetch already in progress, skipping')
      return
    }
    if (isAreasLoaded) {
      return
    }
    isFetching.current = true
    console.log('Areas fetch effect triggered', {
      isAreasLoaded,
      hasFetched: hasFetched.current,
      isFetching: isFetching.current
    })
    let activeRequest = true

    // Add timeout in case fetch hangs
    const timeoutId = setTimeout(() => {
      console.warn('Areas fetch timeout exceeded, forcing initialization')
      if (activeRequest) {
        console.log('TIMEOUT: Setting isAreasLoaded to true')
        dispatch(setIsAreasLoaded(true))
      }
    }, 10000)

    getAreas()
      .then(() => {
        if (activeRequest) {
          clearTimeout(timeoutId)
          hasFetched.current = true
          isFetching.current = false
          console.log('SUCCESS: Setting isAreasLoaded to true')
          dispatch(setIsAreasLoaded(true))
        }
      })
      .catch((error) => {
        if (activeRequest) {
          clearTimeout(timeoutId)
          isFetching.current = false
          console.error('Failed to fetch areas:', error)
          console.log('ERROR: Setting isAreasLoaded to false')
          dispatch(setIsAreasLoaded(false))
          hasFetched.current = false
        }
      })
    return () => {
      activeRequest = false
      clearTimeout(timeoutId)
      isFetching.current = false
    }
  }, [settings?.cloud_run_service_url?.value, settings?.identity_token?.value, dispatch])

  return {
    getAreas,
  }
}
