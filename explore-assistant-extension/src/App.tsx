import React, { useEffect, useState, useRef } from 'react'
import { hot } from 'react-hot-loader/root'
import { Route, Switch, Redirect } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from './store'
import { useLookerFields } from './hooks/useLookerFields'
import { useBigQueryExamples } from './hooks/useBigQueryExamples'
import useSendVertexMessage from './hooks/useSendVertexMessage'
import { useAutoOAuth } from './hooks/useAutoOAuth'
import { useUserAttributes } from './hooks/useUserAttributes'
import { useAdminAuth } from './hooks/useAdminAuth'
import { setInitialTestsCompleted } from './slices/assistantSlice'
import AgentPage from './pages/AgentPage'
import SettingsModal from './pages/AgentPage/Settings'
import { AuthModal } from './components/Auth/AuthModal'
import ConnectionBanner from './components/Banner/ConnectionBanner'
import { Box, CircularProgress, Typography, Button } from '@mui/material'

const ExploreApp = () => {
  const dispatch = useDispatch()
  const { settings, bigQueryTestSuccessful, vertexTestSuccessful, oauth, userAttributesLoaded, initialTestsCompleted } = useSelector((state: RootState) => state.assistant) as any
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)
  
  // For tracking token validation attempts
  const tokenValidationCounter = useRef(0)
  const testsRunCounter = useRef(0)
  const lastCheckedToken = useRef('')
  
  // Load user attributes first
  const { isLoading: isLoadingUserAttributes, error: userAttributesError } = useUserAttributes()
  
  // Skip auto OAuth if settings modal is open
  const { isAuthenticating, hasValidToken, error: oauthError, validationInProgress } = useAutoOAuth(isSettingsOpen)
  
  // Use centralized admin auth
  const { isAdmin, isCheckingAdmin } = useAdminAuth()

  useLookerFields()
  const { testBigQuerySettings } = useBigQueryExamples()
  const { testVertexSettings } = useSendVertexMessage()

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

  // NEW INITIALIZATION FLOW: User attributes → Tests → Conditional settings modal
  useEffect(() => {
    if (!initialTestsCompleted) {
      const runInitialTests = async () => {
        testsRunCounter.current++

        // Validate existing token before running tests
        const existingToken = settings['oauth2_token']?.value;

        if (existingToken && lastCheckedToken.current !== existingToken) {
          lastCheckedToken.current = existingToken
          tokenValidationCounter.current++

          try {
            const tokenInfo = await fetch('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=' + existingToken);

            if (!tokenInfo.ok) {
              console.error('Existing OAuth token is invalid during initial tests');
            }
          } catch (error) {
            console.log('Error validating token in App component:', error);
          }
        }

        if (!bigQueryTestSuccessful) {
          await testBigQuerySettings();
        }

        if (!vertexTestSuccessful) {
          await testVertexSettings();
        }

        // Mark initial tests as completed
        dispatch(setInitialTestsCompleted(true));
      };

      runInitialTests();
    }
  }, [initialTestsCompleted, bigQueryTestSuccessful, vertexTestSuccessful, settings, dispatch, testBigQuerySettings, testVertexSettings]);

  // CONDITIONAL SETTINGS MODAL: Only open if tests fail due to missing critical configuration
  useEffect(() => {
    if (!userAttributesLoaded || !initialTestsCompleted || isCheckingAdmin) {
      return // Wait for initialization to complete
    }

    // Only open settings modal if tests have failed and we're missing critical configuration
    const hasCriticalMissingSettings = !settings['google_oauth_client_id']?.value || 
                                      !settings['vertex_project']?.value ||
                                      !settings['vertex_location']?.value ||
                                      !settings['vertex_model']?.value

    const testsHaveFailed = !bigQueryTestSuccessful || !vertexTestSuccessful

    if (testsHaveFailed && hasCriticalMissingSettings && !isSettingsOpen && !isAuthModalOpen) {
      // For admin users, open the full settings modal
      // For non-admin users, open the simplified auth modal
      if (isAdmin) {
        setIsSettingsOpen(true)
      } else {
        setIsAuthModalOpen(true)
      }
    }
  }, [userAttributesLoaded, initialTestsCompleted, isCheckingAdmin, bigQueryTestSuccessful, vertexTestSuccessful, settings, isSettingsOpen, isAuthModalOpen, isAdmin]);

  // Show error state if OAuth fails or times out
  if (oauthError || showFallbackUI) {
    return (
      <>
        {isAdmin ? (
          <SettingsModal
            open={isSettingsOpen}
            onClose={() => {
              setIsSettingsOpen(false)
              setShowFallbackUI(false)
            }}
          />
        ) : (
          <AuthModal
            open={isAuthModalOpen}
            onClose={() => {
              setIsAuthModalOpen(false)
              setShowFallbackUI(false)
            }}
            title="Authentication Error"
            description="There seems to be an issue with authentication. Please check your OAuth Client ID and try again."
          />
        )}
        <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" height="100vh" p={3}>
          <Typography variant="h6" color="error" gutterBottom>
            {oauthError || 'Authentication Error'}
          </Typography>
          <Typography variant="body1" gutterBottom align="center">
            There seems to be an issue with authentication. Please check your settings and try again.
          </Typography>
          <Box mt={2}>
            <Button 
              variant="contained" 
              color="primary"
              onClick={() => {
                if (isAdmin) {
                  setIsSettingsOpen(true)
                } else {
                  setIsAuthModalOpen(true)
                }
                setShowFallbackUI(false)
              }}
            >
              {isAdmin ? 'Open Settings' : 'Authenticate'}
            </Button>
          </Box>
        </Box>
      </>
    )
  }

  // Show loading state while user attributes are being loaded or admin status is being checked
  if (isLoadingUserAttributes || !userAttributesLoaded || isCheckingAdmin) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Box ml={2}>Loading configuration...</Box>
      </Box>
    )
  }

  if (isAuthenticating) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Box ml={2}>Authenticating with Google...</Box>
      </Box>
    )
  }
 
  // Always show banner initially since we're not using localStorage anymore
  const bannerInitialState = true

  return (
    <>
      {isAdmin ? (
        <SettingsModal
          open={isSettingsOpen}
          onClose={() => {
            setIsSettingsOpen(false)
          }}
        />
      ) : (
        <AuthModal
          open={isAuthModalOpen}
          onClose={() => {
            setIsAuthModalOpen(false)
          }}
        />
      )}
      
      {bigQueryTestSuccessful && vertexTestSuccessful ? (
        <>
          <ConnectionBanner initialVisible={bannerInitialState} />
          <Switch>
            <Route path="/index" exact>
              <AgentPage />
            </Route>
            <Route>
              <Redirect to="/index" />
            </Route>
          </Switch>
        </>
      ) : (
        // Show setup UI when tests haven't passed
        <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" height="100vh" p={3}>
          <Typography variant="h5" gutterBottom>
            Welcome to Explore Assistant
          </Typography>
          <Typography variant="body1" gutterBottom align="center">
            Please complete the initial setup to get started.
          </Typography>
          <Box mt={2}>
            <Button 
              variant="contained" 
              color="primary"
              onClick={() => {
                if (isAdmin) {
                  setIsSettingsOpen(true)
                } else {
                  setIsAuthModalOpen(true)
                }
              }}
            >
              {isAdmin ? 'Open Settings' : 'Authenticate'}
            </Button>
          </Box>
          <Box mt={3}>
            <Typography variant="body2" style={{ color: bigQueryTestSuccessful ? '#4caf50' : '#f44336' }}>
              BigQuery Test: {bigQueryTestSuccessful ? '✅ Passed' : '❌ Failed'}
            </Typography>
            <Typography variant="body2" style={{ color: vertexTestSuccessful ? '#4caf50' : '#f44336' }}>
              Vertex AI Test: {vertexTestSuccessful ? '✅ Passed' : '❌ Failed'}
            </Typography>
          </Box>
        </Box>
      )}
    </>
  )
}

export const App = hot(ExploreApp)
