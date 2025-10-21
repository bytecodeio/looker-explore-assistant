import React, { useEffect, useState, useRef } from 'react'
import { hot } from 'react-hot-loader/root'
import { Route, Switch, Redirect } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from './store'
import { useLookerFields } from './hooks/useLookerFields'
import { useBigQueryExamples } from './hooks/useBigQueryExamples'
import useSendCloudRunMessage from './hooks/useSendCloudRunMessage'
import { useExtensionContext } from './hooks/useExtensionContext'
import {
  setInitialTestsCompleted,
} from './slices/assistantSlice'
import AgentPage from './pages/AgentPage'
import QueryPromotionPage from './pages/QueryPromotionPage'
import VectorPage from './pages/VectorPage'
// Settings UI removed - configuration now comes from environment variables
import { Box, CircularProgress, Typography, Button } from '@material-ui/core'

const ExploreApp = () => {
  const { bigQueryTestSuccessful, vertexTestSuccessful, userAttributesLoaded, initialTestsCompleted } = useSelector((state: RootState) => state.assistant) as any
  
  // Load extension context first (renamed for clarity but keeping same interface)
  const { isLoading: isLoadingExtensionContext, error: extensionContextError } = useExtensionContext()

  useLookerFields()

  // Show loading state while extension context is being loaded
  if (isLoadingExtensionContext || !userAttributesLoaded) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Box ml={2}>Loading configuration...</Box>
      </Box>
    )
  }

  return (
    <>
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
