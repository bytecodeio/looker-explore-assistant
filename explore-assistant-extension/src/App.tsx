import React, { useEffect, useState, useRef } from 'react'
import { hot } from 'react-hot-loader/root'
import { Route, Switch, Redirect } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from './store'
import { useLookerFields } from './hooks/useLookerFields'
import { useBigQueryExamples } from './hooks/useBigQueryExamples'
import useSendCloudRunMessage from './hooks/useSendCloudRunMessage'
import { useAutoOAuth } from './hooks/useAutoOAuth'
import { useExtensionContext } from './hooks/useExtensionContext'
import {
  setInitialTestsCompleted,
} from './slices/assistantSlice'
import AgentPage from './pages/AgentPage'
import QueryPromotionPage from './pages/QueryPromotionPage'
import VectorPage from './pages/VectorPage'
import SettingsModal from './pages/AgentPage/Settings'
import { Box, CircularProgress, Typography, Button } from '@material-ui/core'

// Debug flag for OAuth flow
const AUTH_DEBUG = false

const ExploreApp = () => {
  const { settings, bigQueryTestSuccessful, vertexTestSuccessful, oauth, userAttributesLoaded, initialTestsCompleted } = useSelector((state: RootState) => state.assistant) as any
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  
  // Load extension context first (renamed for clarity but keeping same interface)
  const { isLoading: isLoadingExtensionContext, error: extensionContextError } = useExtensionContext()
  
  // Skip auto OAuth if settings modal is open
  const { isAuthenticating, hasValidToken, error: oauthError, validationInProgress } = useAutoOAuth(isSettingsOpen)

  useLookerFields()

  // Add timeout for OAuth process
  const [showFallbackUI, setShowFallbackUI] = useState(false)
  
  useEffect(() => {
    const oauthTimeout = setTimeout(() => {
      if (isAuthenticating) {
        console.warn('OAuth taking too long, showing fallback UI')
        setShowFallbackUI(true)
      }
    }, 15000) // 15 second timeout

    return () => clearTimeout(oauthTimeout)
  }, [isAuthenticating])

  // Show error state if OAuth fails or times out - default to popup guidance since most OAuth errors are popup-related
  if (oauthError || showFallbackUI) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" height="100vh" p={3} maxWidth="600px" mx="auto">
        <Typography variant="h6" color="error" gutterBottom>
          Pop-up Blocked
        </Typography>
        <Typography variant="body1" gutterBottom align="center" sx={{ mb: 2 }}>
          Your browser blocked the authorization pop-up window. To use this extension, you need to allow pop-ups for this site.
        </Typography>
        
        <Box sx={{ textAlign: 'left', mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'bold' }}>
            How to allow pop-ups:
          </Typography>
          <Typography variant="body2" component="div">
            <strong>Chrome:</strong>
            <br />• Click the pop-up blocked icon in the address bar
            <br />• Select "Always allow pop-ups from this site"
            <br /><br />
            <strong>Firefox:</strong>
            <br />• Click the shield icon in the address bar  
            <br />• Select "Allow pop-ups for this site"
            <br /><br />
            <strong>Safari:</strong>
            <br />• Go to Safari → Preferences → Websites → Pop-up Windows
            <br />• Find this site and set to "Allow"
            <br /><br />
            <strong>Edge:</strong>
            <br />• Click the pop-up blocked notification in the address bar
            <br />• Select "Always allow"
          </Typography>
        </Box>
        
        <Box mt={2}>
          <Button 
            variant="contained" 
            color="primary"
            onClick={() => window.location.reload()}
          >
            Reload Page
          </Button>
        </Box>
      </Box>
    )
  }

  // Show loading state while extension context is being loaded
  if (isLoadingExtensionContext || !userAttributesLoaded) {
    AUTH_DEBUG && console.log('Showing extension context loading indicator')
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Box ml={2}>Loading configuration...</Box>
      </Box>
    )
  }

  if (isAuthenticating) {
    AUTH_DEBUG && console.log('Showing authentication progress indicator')
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Box ml={2}>Authenticating with Google...</Box>
      </Box>
    )
  }
  AUTH_DEBUG && console.log('Rendering main app view. Settings open:', isSettingsOpen, 'BQ/Vertex tests successful:', bigQueryTestSuccessful, vertexTestSuccessful)

  return (
    <>
      <SettingsModal
        open={isSettingsOpen}
        onClose={() => {
          AUTH_DEBUG && console.log('Settings modal closed')
          setIsSettingsOpen(false)
        }}
      />
      <Switch>
        <Route path="/index" exact>
          <AgentPage />
        </Route>
        <Route path="/promotion" exact>
          <QueryPromotionPage />
        </Route>
        <Route path="/vector-setup" exact>
          <VectorPage />
        </Route>
        <Route>
          <Redirect to="/index" />
        </Route>
      </Switch>
      {/* Test status banner removed as per user request */}
    </>
  )
}

export const App = hot(ExploreApp)
