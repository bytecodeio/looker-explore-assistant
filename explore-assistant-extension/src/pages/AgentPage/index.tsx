import React, { useCallback, useEffect, useRef, useState, useContext } from 'react'
import PromptInput from './PromptInput'
import Sidebar from './Sidebar'
import { v4 as uuidv4 } from 'uuid'

import './style.css'
import SamplePrompts from '../../components/SamplePrompts'
import { ExploreEmbed } from '../../components/ExploreEmbed'
import { RootState } from '../../store'
import { useDispatch, useSelector } from 'react-redux'
import useSendVertexMessage from '../../hooks/useSendVertexMessage'
import { useConversationExplore } from '../../hooks/useConversationExplore'
import {
  addMessage,
  AssistantState,
  closeSidePanel,
  openSidePanel,
  setCurrenExplore,
  setIsQuerying,
  setQuery,
  setSidePanelExploreParams,
  updateCurrentThread,
  updateLastHistoryEntry,
} from '../../slices/assistantSlice'
import MessageThread from './MessageThread'
import clsx from 'clsx'
import { Close } from '@material-ui/icons'
import {
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  SelectChangeEvent,
  Tooltip,
} from '@mui/material'
import ConnectionBanner from '../../components/Banner/ConnectionBanner'
import { getRelativeTimeString } from '../../utils/time'

const toCamelCase = (input: string): string => {
  // Remove underscores, make following letter uppercase
  let result = input.replace(
    /_([a-z])/g,
    (_match, letter) => ' ' + letter.toUpperCase(),
  )

  // Capitalize the first letter of the string
  result = result.charAt(0).toUpperCase() + result.slice(1)

  return result
}

const AgentPage = () => {
  const endOfMessagesRef = useRef<HTMLDivElement>(null) // Ref for the last message
  const dispatch = useDispatch()
  const [expanded, setExpanded] = useState(false)
  const { generateExploreParams, isSummarizationPrompt, summarizePrompts } =
    useSendVertexMessage()
  const { findAndSelectExplore, isSelectingExplore } = useConversationExplore()

  const {
    isChatMode,
    query,
    isQuerying,
    currentExploreThread,
    currentExplore,
    sidePanel,
    examples,
    semanticModels,
    isBigQueryMetadataLoaded,
    isSemanticModelLoaded,
    showConnectionBanner,
  } = useSelector((state: RootState) => state.assistant as AssistantState)

  const explores = Object.keys(examples.exploreSamples).map((key) => {
    const exploreParts = key.split(':')
    return {
      exploreKey: key,
      modelName: exploreParts[0],
      exploreId: exploreParts[1],
    }
  })

  const scrollIntoView = useCallback(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [endOfMessagesRef])

  useEffect(() => {
    scrollIntoView()
  }, [currentExploreThread, query, isQuerying])

  const submitMessage = useCallback(async () => {
    if (query === '') {
      return
    }

    dispatch(setIsQuerying(true))

    // update the prompt list
    let promptList = [query]
    if (currentExploreThread && currentExploreThread.promptList) {
      promptList = [...currentExploreThread.promptList, query]
    }

    dispatch(
      updateCurrentThread({
        promptList,
      }),
    )

    // add the user message
    dispatch(
      addMessage({
        uuid: uuidv4(),
        message: query,
        actor: 'user',
        createdAt: Date.now(),
        type: 'text',
      }),
    )

    // Clear the query
    dispatch(setQuery(''))
    
    // First, check if we have a selected explore - if not, find one based on the query
    const hasExplore = currentExplore && currentExplore.exploreId && currentExplore.modelName
    if (!hasExplore) {
      const exploreSelected = await findAndSelectExplore(query)
      if (!exploreSelected) {
        // If explore selection failed, stop processing and set isQuerying to false
        dispatch(setIsQuerying(false))
        return
      }
      // Give a moment for the UI to update with explore selection messages
      await new Promise(resolve => setTimeout(resolve, 500))
    }

    // If the semanticModels aren't loaded yet or we don't have an explore key, stop here
    if (!semanticModels || !currentExplore.exploreKey) {
      dispatch(setIsQuerying(false))
      return
    }

    const semanticModel = semanticModels[currentExplore.exploreKey]

    if (!semanticModel) {
      console.error('No semantic model found for', currentExplore.exploreKey)
      dispatch(setIsQuerying(false))
      return
    }

    const dimensions = semanticModel.dimensions
    const measures = semanticModel.measures
    const exploreKey = currentExplore.exploreKey
    const exploreGenerationExamples = examples.exploreGenerationExamples[exploreKey]

    if (!dimensions || !measures) {
      console.error('No dimensions or measures found in semantic model')
      dispatch(setIsQuerying(false))
      return
    }

    // check if the user is asking for a data summarization
    const isDataSummary = await isSummarizationPrompt(query)

    if (isDataSummary) {
      // and the current params are populated
      if (
        currentExploreThread?.exploreParams &&
        currentExploreThread?.exploreParams.fields &&
        currentExploreThread?.exploreParams.fields.length > 0
      ) {
        // add a summarize type message
        dispatch(
          addMessage({
            uuid: uuidv4(),
            actor: 'system',
            exploreParams: currentExploreThread.exploreParams,
            createdAt: Date.now(),
            type: 'summarize',
            summary: '',
          }),
        )

        // We're done!
        dispatch(setIsQuerying(false))
        return
      }
    }

    // summarize using the list of prompts and potentially handle a summary request
    const promptSummary = await summarizePrompts(promptList)

    // generate query parameters from the prompt
    const explorerParamsResponse = await generateExploreParams(
      promptSummary,
      dimensions,
      measures,
      exploreGenerationExamples || [],
    )

    // save the explore params
    dispatch(
      updateCurrentThread({
        exploreParams: explorerParamsResponse,
      }),
    )

    // add the explorer message
    if (explorerParamsResponse) {
      dispatch(
        addMessage({
          uuid: uuidv4(),
          exploreParams: explorerParamsResponse,
          summarizedPrompt: promptSummary,
          actor: 'system',
          createdAt: Date.now(),
          type: 'explore',
        }),
      )
    }

    // scroll to bottom of message thread
    scrollIntoView()

    // update the history with the current contents of the thread
    dispatch(updateLastHistoryEntry())
    dispatch(setIsQuerying(false))
  }, [
    query, 
    semanticModels, 
    examples, 
    currentExplore, 
    currentExploreThread, 
    findAndSelectExplore
  ])

  const isDataLoaded = isBigQueryMetadataLoaded && isSemanticModelLoaded

  useEffect(() => {
    if (!query || query === '' || !isDataLoaded) {
      return
    }

    submitMessage()
    scrollIntoView()
  }, [query, isDataLoaded])

  const toggleDrawer = () => {
    setExpanded(!expanded)
  }

  const handleExploreChange = (event: SelectChangeEvent) => {
    const exploreKey = event.target.value
    const [modelName, exploreId] = exploreKey.split(':')
    dispatch(
      setCurrenExplore({
        modelName,
        exploreId,
        exploreKey,
      }),
    )
  }

  const isAgentReady = isBigQueryMetadataLoaded && isSemanticModelLoaded

  console.log('agent ready?', isAgentReady, isBigQueryMetadataLoaded, isSemanticModelLoaded)
  
  if (!isAgentReady) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="flex flex-col space-y-4 mx-auto max-w-2xl p-4">
          <h1 className="text-5xl font-bold">
            <span className="bg-clip-text text-transparent  bg-gradient-to-r from-pink-500 to-violet-500">
              Hello.
            </span>
          </h1>
          <h1 className="text-3xl text-gray-400">
            Getting everything ready...
          </h1>
          <div className="max-w-2xl text-blue-300">
            <LinearProgress color="inherit" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex">
      {/* Sidebar */}
      <Sidebar expanded={expanded} toggleDrawer={toggleDrawer} />

      {/* Content */}
      <div className="flex-1">
        <div className={`transition-all duration-300 ease-in-out h-screen`}>
          {/* Content area */}
          {showConnectionBanner && <ConnectionBanner />}
          {isBigQueryMetadataLoaded && isSemanticModelLoaded && explores.length > 0 && (
            <div className="p-2 bg-white shadow text-gray-500 text-xs">
              <ol className="flex items-center">
                <li className="flex items-center">
                  <FormControl size="small">
                    <InputLabel>Explore</InputLabel>
                    <Select
                      value={currentExplore.exploreKey}
                      onChange={handleExploreChange}
                      label="Explore"
                      size="small"
                      style={{ minWidth: '200px' }}
                    >
                      {explores.map((explore) => (
                        <MenuItem
                          key={explore.exploreKey}
                          value={explore.exploreKey}
                        >
                          {toCamelCase(explore.exploreId || '')}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <div className="mx-2">
                    <div className="w-1 h-1 bg-gray-300 rounded-full"></div>
                  </div>

                  <div className="flex flex-row items-center">
                    <div className="ml-4 text-xs font-medium text-gray-500 hover:text-gray-700">
                      Chat (started{' '}
                      {getRelativeTimeString(
                        currentExploreThread?.createdAt
                          ? new Date(currentExploreThread.createdAt)
                          : new Date(),
                      )}
                      )
                    </div>
                  </div>
                </li>
              </ol>
            </div>
          )}
          {isChatMode ? (
            <div className="relative flex flex-row h-screen px-4 pt-6 ">
              <div
                className={clsx(
                  'flex flex-col relative',
                  sidePanel.isSidePanelOpen ? 'w-2/5' : 'w-full',
                )}
              >
                <div className="flex-grow overflow-y-auto max-h-full mb-36 ">
                  <div className="max-w-4xl mx-auto mt-8">
                    <MessageThread endOfMessageRef={endOfMessagesRef} />
                  </div>
                </div>
                <div
                  className={`fixed bottom-0 left-0 right-0 max-w-4xl px-10 mx-auto pb-6`}
                >
                  <PromptInput />
                </div>
              </div>
              {/* Explore side pane */}
              {sidePanel.isSidePanelOpen && (
                <div className="w-3/5 relative bg-white rounded-lg shadow-md ml-4 max-h-full overflow-y-auto">
                  <div className="flex flex-wrap items-center p-2 border-b mb-2">
                    <div className="flex-1 font-semibold">Explore</div>
                    <div>
                      <button
                        onClick={() => dispatch(closeSidePanel())}
                        className="text-gray-500 hover:text-gray-700"
                      >
                        <Close fontSize="small" />
                      </button>
                    </div>
                  </div>
                  <div className="px-2 pb-2">
                    <ExploreEmbed
                      exploreParams={sidePanel.exploreParams}
                      modelName={currentExplore.modelName}
                      exploreId={currentExplore.exploreId}
                      height="calc(100vh - 100px)"
                    />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="w-full max-w-5xl mx-auto px-8">
              <div className="flex flex-col items-center justify-center my-auto">
                <div className="mt-12">
                  <h1 className="text-3xl font-light text-gray-800 mb-8 flex flex-col items-center">
                    <div className="mb-4">
                      Explore with
                      <span className="font-bold mb-2 ml-2 bg-clip-text text-transparent bg-gradient-to-r from-pink-500 to-violet-500">
                        {' '}
                        AI
                      </span>
                    </div>
                  </h1>
                  {(!isSemanticModelLoaded || !isBigQueryMetadataLoaded) && (
                    <>
                      <LinearProgress />
                      <div className="mt-4 text-center">
                        <p className="mb-4 text-orange-600">
                          Waiting for data to load...
                        </p>
                      </div>
                    </>
                  )}
                  <div className="flex flex-col items-center">
                    <SamplePrompts />

                    <div className="mt-6 max-w-xl">
                      <PromptInput />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AgentPage
