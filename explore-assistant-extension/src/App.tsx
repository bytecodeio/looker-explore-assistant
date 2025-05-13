import React, { useEffect, useState } from 'react'
import { hot } from 'react-hot-loader/root'
import { Route, Switch, Redirect } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from './store'
import { useLookerFields } from './hooks/useLookerFields'
import { useBigQueryExamples } from './hooks/useBigQueryExamples'
import useSendVertexMessage from './hooks/useSendVertexMessage'
import { useAutoOAuth } from './hooks/useAutoOAuth'
import { TableInitializer } from './components/Setup/TableInitializer'
import AgentPage from './pages/AgentPage'
import SettingsModal from './pages/AgentPage/Settings'
import ConnectionBanner from './components/Banner/ConnectionBanner'
import { Box, CircularProgress, Typography } from '@material-ui/core'

const ExploreApp = () => {
  const dispatch = useDispatch()
  const { settings, bigQueryTestSuccessful, vertexTestSuccessful } = useSelector((state: RootState) => state.assistant) as any
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isTableInitialized, setIsTableInitialized] = useState(false)
  const [showTableInitializer, setShowTableInitializer] = useState(false)
  
  // Skip auto OAuth if settings modal is open
  const { isAuthenticating } = useAutoOAuth(isSettingsOpen)

  useLookerFields()
  const { testBigQuerySettings } = useBigQueryExamples()
  const { testVertexSettings } = useSendVertexMessage()

  useEffect(() => {
    const missingSettings = Object.values(settings).some(setting => !setting?.value)
    if (missingSettings) {
      setIsSettingsOpen(true)
    } 
  }, [settings])

  useEffect(() => {
    const runTests = async () => {
      // Validate existing token before running tests
      const existingToken = settings['oauth2_token']?.value;
      if (existingToken) {
        const tokenInfo = await fetch('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=' + existingToken);
        if (!tokenInfo.ok) {
          console.error('Existing OAuth token is invalid, triggering re-authentication');
          setIsSettingsOpen(true);
          return;
        }
      }

      testBigQuerySettings();
      testVertexSettings();
    };

    if (!bigQueryTestSuccessful || !vertexTestSuccessful) {
      runTests();
    } else if (bigQueryTestSuccessful && vertexTestSuccessful && !isTableInitialized && !showTableInitializer) {
      // Once settings are confirmed working, show the table initializer
      setShowTableInitializer(true);
    }
  }, [testBigQuerySettings, testVertexSettings, bigQueryTestSuccessful, vertexTestSuccessful, settings, isTableInitialized, showTableInitializer]);

  const handleTablesInitialized = () => {
    setIsTableInitialized(true);
    setShowTableInitializer(false);
  };

  if (isAuthenticating) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <div ml={2}>Authenticating with Google...</div>
      </Box>
    )
  }
  console.log('settings, bq,vt', !isSettingsOpen , bigQueryTestSuccessful, vertexTestSuccessful)

  // Check if banner was previously dismissed
  const bannerInitialState = localStorage.getItem('connectionBannerDismissed') !== 'true'

  return (
    <>
      <SettingsModal
        open={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
      { bigQueryTestSuccessful && vertexTestSuccessful && (
        <>
          {showTableInitializer ? (
            <TableInitializer onInitialized={handleTablesInitialized} />
          ) : isTableInitialized && (
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
          )}
        </>
      )}
    </>
  )
}

export const App = hot(ExploreApp)
