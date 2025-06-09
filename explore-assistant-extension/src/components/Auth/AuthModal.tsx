import React, { useState } from 'react'
import { Modal, Box, Typography, TextField } from '@mui/material'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from '../../store'
import { setSetting, AssistantState } from '../../slices/assistantSlice'
import { useAdminAuth } from '../../hooks/useAdminAuth'
import { AuthButton } from './AuthButton'

interface AuthModalProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
}

/**
 * Centralized authentication modal component
 * Works for both admin and non-admin users
 */
export const AuthModal: React.FC<AuthModalProps> = ({
  open,
  onClose,
  title = 'Authentication Required',
  description = 'Please enter your Google OAuth Client ID and authenticate to continue.'
}) => {
  const dispatch = useDispatch()
  const { settings } = useSelector((state: RootState) => state.assistant as AssistantState)
  const { isAdmin, hasValidToken, oauthError } = useAdminAuth()
  
  const [clientId, setClientId] = useState(settings['google_oauth_client_id']?.value || '')

  const handleSaveClientId = (value: string) => {
    setClientId(value)
    dispatch(setSetting({ id: 'google_oauth_client_id', value }))
  }

  const handleAuthSuccess = () => {
    // Close modal after successful authentication
    setTimeout(() => {
      onClose()
    }, 1000)
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      aria-labelledby="auth-modal-title"
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Box
        sx={{
          width: '90%',
          maxWidth: 500,
          bgcolor: 'background.paper',
          border: '2px solid #000',
          borderRadius: 2,
          boxShadow: 24,
          p: 4,
        }}
      >
        <Typography
          id="auth-modal-title"
          variant="h5"
          component="h2"
          gutterBottom
          sx={{
            background: 'linear-gradient(45deg, #ec4899 30%, #8b5cf6 90%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            textAlign: 'center'
          }}
        >
          {title}
        </Typography>

        <Typography variant="body1" sx={{ mb: 3, textAlign: 'center' }}>
          {description}
        </Typography>

        {oauthError && (
          <Box sx={{ mb: 2, p: 2, bgcolor: '#ffebee', border: '1px solid #f44336', borderRadius: 1 }}>
            <Typography variant="body2" color="error">
              {oauthError}
            </Typography>
          </Box>
        )}

        <Box sx={{ mb: 3 }}>
          <TextField
            fullWidth
            label="Google OAuth Client ID"
            value={clientId}
            onChange={(e) => handleSaveClientId(e.target.value)}
            placeholder="Enter your Google OAuth Client ID"
            variant="outlined"
            size="small"
          />
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
          <AuthButton
            onAuthSuccess={handleAuthSuccess}
            showStatus={true}
            clientIdRequired={true}
          />
        </Box>

        {isAdmin && (
          <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary' }}>
            As an admin, you can also access the full Settings panel for advanced configuration.
          </Typography>
        )}
      </Box>
    </Modal>
  )
}
