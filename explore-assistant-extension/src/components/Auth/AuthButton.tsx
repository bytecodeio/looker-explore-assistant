import React from 'react'
import { Button, Box, Typography } from '@mui/material'
import { useAdminAuth } from '../../hooks/useAdminAuth'

interface AuthButtonProps {
  variant?: 'contained' | 'outlined' | 'text'
  size?: 'small' | 'medium' | 'large'
  onAuthSuccess?: () => void
  showStatus?: boolean
  clientIdRequired?: boolean
}

/**
 * Centralized authentication button component
 * Handles both admin and non-admin authentication flows
 */
export const AuthButton: React.FC<AuthButtonProps> = ({
  variant = 'contained',
  size = 'medium',
  onAuthSuccess,
  showStatus = false,
  clientIdRequired = true
}) => {
  const { doOAuth, isAuthenticating, hasValidToken, oauthError } = useAdminAuth()

  const handleAuthenticate = async () => {
    const success = await doOAuth()
    if (success && onAuthSuccess) {
      onAuthSuccess()
    }
  }

  return (
    <Box>
      <Button
        onClick={handleAuthenticate}
        variant={variant}
        size={size}
        disabled={isAuthenticating || (clientIdRequired && !hasValidToken)}
        color="primary"
      >
        {isAuthenticating ? 'Authenticating...' : 'Authenticate'}
      </Button>
      
      {showStatus && (
        <Box mt={1}>
          <Typography variant="body2" color={hasValidToken ? 'primary' : 'textSecondary'}>
            Status: {hasValidToken ? '✅ Authenticated' : '❌ Not Authenticated'}
          </Typography>
          {oauthError && (
            <Typography variant="body2" color="error">
              Error: {oauthError}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  )
}
