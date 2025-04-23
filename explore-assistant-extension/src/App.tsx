import React, { useEffect, useState } from 'react'
import { hot } from 'react-hot-loader/root'
import { Route, Switch, Redirect } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from './store'
import { useLookerFields } from './hooks/useLookerFields'
import { useBigQueryExamples } from './hooks/useBigQueryExamples'
import AgentPage from './pages/AgentPage'
import SettingsModal from './pages/AgentPage/Settings'

const ExploreApp = () => {
  const dispatch = useDispatch()
  const { settings, bigQueryTestSuccessful } = useSelector((state: RootState) => state.assistant) as any
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  useLookerFields()
  const { testBigQuerySettings } = useBigQueryExamples()

  useEffect(() => {
    const missingSettings = Object.values(settings).some(setting => !setting?.value)
    if (missingSettings) {
      setIsSettingsOpen(true)
    } 
  }, [settings])

  useEffect(() => {
    const runTests = async () => {
      testBigQuerySettings()
    }
    if (!bigQueryTestSuccessful) {
      runTests()
    }
  }, [testBigQuerySettings, bigQueryTestSuccessful, dispatch, settings])

  return (
    <>
      <SettingsModal
        open={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
      {!isSettingsOpen && bigQueryTestSuccessful && (
        <Switch>
          <Route path="/index" exact>
            <AgentPage />
          </Route>
          <Route>
            <Redirect to="/index" />
          </Route>
        </Switch>
      )}
    </>
  )
}

export const App = hot(ExploreApp)
