import { useState, useEffect, useContext } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { RootState } from '../store'
import {
  setSetting,
  setOAuthError,
  setOAuthAuthenticating,
  AssistantState,
} from '../slices/assistantSlice'

export interface AdminAuthResult {
  isAdmin: boolean
  isCheckingAdmin: boolean
  doOAuth: () => Promise<boolean>
  isAuthenticating: boolean
  hasValidToken: boolean
  oauthError: string | null
}

/**
 * Centralized hook for admin status checking and OAuth authentication
 */
export const useAdminAuth = (): AdminAuthResult => {
  const { core40SDK, extensionSDK } = useContext(ExtensionContext)
  const dispatch = useDispatch()
  const { settings, oauth } = useSelector((state: RootState) => state.assistant as AssistantState)
  
  const [isAdmin, setIsAdmin] = useState(false)
  const [isCheckingAdmin, setIsCheckingAdmin] = useState(true)
  
  const GOOGLE_SCOPES = 'https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email'
  const GOOGLE_CLIENT_ID = settings['google_oauth_client_id']?.value as string || ''

  // Check admin status
  useEffect(() => {
    const checkAdminStatus = async () => {
      if (!core40SDK) {
        setIsCheckingAdmin(false)
        return
      }

      try {
        const response: any = await core40SDK.ok(core40SDK.me())
        
        let adminStatus = false
        
        // First, get the actual admin role ID by searching for roles with name 'admin'
        let adminRoleId: string | null = null
        try {
          const adminRoles = await core40SDK.ok(core40SDK.search_roles({
            name: 'admin'
          }))
          
          if (adminRoles && adminRoles.length > 0) {
            adminRoleId = adminRoles[0].id || null
          }
        } catch (roleError) {
          console.warn('Could not fetch admin role:', roleError)
        }
        
        // Enhanced admin check with multiple fallbacks
        // 1. Check is_iam_admin if it exists and is false, but still continue to role check
        if (typeof response.is_iam_admin === 'boolean') {
          adminStatus = response.is_iam_admin
        }

        // 2. Always check role_ids for admin role (even if is_iam_admin is false)
        if (Array.isArray(response.role_ids)) {
          // Check against the dynamically fetched admin role ID
          if (adminRoleId && (response.role_ids.includes(adminRoleId) || response.role_ids.includes(parseInt(adminRoleId)))) {
            adminStatus = true
          }
        }
        
        setIsAdmin(adminStatus)
      } catch (error) {
        console.error('Error checking admin status:', error)
        setIsAdmin(false) // Default to false on error
      } finally {
        setIsCheckingAdmin(false)
      }
    }
    
    checkAdminStatus()
  }, [core40SDK])

  // OAuth authentication function
  const doOAuth = async (): Promise<boolean> => {
    if (!GOOGLE_CLIENT_ID) {
      dispatch(setOAuthError('Google OAuth Client ID is required for authentication'))
      return false
    }

    if (!extensionSDK) {
      dispatch(setOAuthError('Extension SDK not available'))
      return false
    }

    dispatch(setOAuthAuthenticating(true))
    dispatch(setOAuthError(null))

    try {
      const response = await extensionSDK.oauth2Authenticate(
        'https://accounts.google.com/o/oauth2/v2/auth',
        {
          client_id: GOOGLE_CLIENT_ID,
          scope: GOOGLE_SCOPES,
          response_type: 'token',
        }
      )

      const { access_token } = response
      if (access_token) {
        dispatch(setSetting({ id: 'oauth2_token', value: access_token }))
        return true
      }
      dispatch(setOAuthError('Failed to receive access token from OAuth flow'))
      return false
    } catch (error: any) {
      dispatch(setOAuthError(`OAuth authentication failed: ${error.message || 'Unknown error'}`))
      return false
    } finally {
      dispatch(setOAuthAuthenticating(false))
    }
  }

  return {
    isAdmin,
    isCheckingAdmin,
    doOAuth,
    isAuthenticating: oauth.isAuthenticating,
    hasValidToken: !!settings['oauth2_token']?.value,
    oauthError: oauth.error
  }
}
