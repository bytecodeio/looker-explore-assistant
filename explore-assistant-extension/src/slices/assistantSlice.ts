import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { v4 as uuidv4 } from 'uuid'

export interface ExploreParams {
  fields?: string[]
  filters?: Record<string, string>
  pivots?: string[]
  vis_config?: any
  sorts?: string[]
  limit?: string

}

// Settings interfaces removed - configuration now comes from environment variables

export interface ExploreSamples {
  [exploreKey: string]: Sample[]
}

export interface ExploreExamples {
  [exploreKey: string]: {
    input: string
    output: string
  }[]
}

export interface RefinementExamples {
  [exploreKey: string]: {
    input: string[]
    output: string
  }[]
}

export interface Area {
  area: string
  explore_keys: string[]
  explore_details: {
    [exploreKey: string]: {
      description: string
      display_name: string
    }
  }
}

interface Field {
  name: string
  type: string
  description: string
  tags: string[]
}

interface Sample {
  category: string
  prompt: string
}

export interface Message {
  uuid: string
  message: string
  actor: 'user' | 'system'
  createdAt: number
  type: 'text'
  intent?: 'exploreRefinement' | 'summarize' | 'dataQuestion'
}

export interface ExploreMessage {
  uuid: string
  exploreParams: ExploreParams
  actor: 'system'
  createdAt: number
  type: 'explore'
  summarizedPrompt: string
  summary?: string
  vectorSearchUsed?: VectorSearchUsage[]
  vectorSearchSummary?: VectorSearchSummaryInfo
}

export interface VectorSearchUsage {
  function: 'search_semantic_fields' | 'lookup_field_values'
  args: Record<string, any>
  phase: 'explore_selection' | 'parameter_generation'
}

export interface VectorSearchSummaryInfo {
  total_vector_searches: number
  search_semantic_fields_count: number
  lookup_field_values_count: number
  user_messages: string[]
  detailed_usage: VectorSearchUsage[]
}

export interface SummarizeMesage {
  uuid: string
  exploreParams: ExploreParams
  actor: 'system'
  createdAt: number
  type: 'summarize'
  summary: string
}

export type ChatMessage = Message | ExploreMessage | SummarizeMesage

export type ExploreThread = {
  uuid: string
  exploreId: string
  modelName: string
  exploreKey: string
  messages: ChatMessage[]
  exploreParams: ExploreParams
  summarizedPrompt: string
  promptList: string[]
  createdAt: number
}


export interface SemanticModel {
  dimensions: Field[]
  measures: Field[]
  exploreKey: string
  exploreId: string
  modelName: string
  description: string
}

export interface AssistantState {
  isQuerying: boolean
  isChatMode: boolean
  currentExploreThread: ExploreThread | null
  currentExplore: {
    exploreKey: string
    modelName: string
    exploreId: string
  }
  selectedArea: string | null
  selectedExplores: string[] // Array of selected explore keys
  availableAreas: Area[]
  isAreasLoaded: boolean
  sidePanel: {
    isSidePanelOpen: boolean
    exploreParams: ExploreParams
  }
  history: ExploreThread[]
  semanticModels: {
    [exploreKey: string]: SemanticModel
  }
  query: string
  examples: {
    exploreEntries: any[],
    exploreGenerationExamples: ExploreExamples
    exploreRefinementExamples: RefinementExamples
    exploreSamples: ExploreSamples
  },
  isBigQueryMetadataLoaded: boolean,
  isSemanticModelLoaded: boolean,
  testsSuccessful: boolean
  bigQueryTestSuccessful: boolean
  vertexTestSuccessful: boolean
  showConnectionBanner: boolean,
  // User attribute loading state
  userAttributesLoaded: boolean,
  initialTestsCompleted: boolean
}

export const newThreadState = () => {
  const thread: ExploreThread = {    
    uuid: uuidv4(),
    exploreKey: '',
    exploreId: '',
    modelName: '',
    messages: [],
    exploreParams: {},
    summarizedPrompt: '',
    promptList: [],
    createdAt: Date.now()
  }
  return thread
}

export const initialState: AssistantState = {
  isQuerying: false,
  isChatMode: false,
  currentExploreThread: null,
  currentExplore: {
    exploreKey: '',
    modelName: '',
    exploreId: ''
  },
  selectedArea: null,
  selectedExplores: [],
  availableAreas: [],
  isAreasLoaded: false,
  sidePanel: {
    isSidePanelOpen: false,
    exploreParams: {},
  },
  history: [],
  query: '',
  semanticModels: {},
  examples: {
    exploreEntries: [],
    exploreGenerationExamples: {},
    exploreRefinementExamples: {},
    exploreSamples: {},
  },
  isBigQueryMetadataLoaded: false,
  isSemanticModelLoaded: false,
  testsSuccessful: false,
  bigQueryTestSuccessful: false,
  vertexTestSuccessful: false,
  showConnectionBanner: true,
  // User attribute loading state
  userAttributesLoaded: false,
  initialTestsCompleted: false
}

export const assistantSlice = createSlice({
  name: 'assistant',
  initialState,
  reducers: {
    resetExploreAssistant: () => {
      return initialState
    },
    setIsQuerying: (state, action: PayloadAction<boolean>) => {
      state.isQuerying = action.payload
    },
    setIsChatMode: (state, action: PayloadAction<boolean>) => {
      state.isChatMode = action.payload
    },
    resetChatMode: (state) => {
      state.isChatMode = false
      assistantSlice.caseReducers.resetChat(state)
    },
    openSidePanel: (state) => {
      state.sidePanel.isSidePanelOpen = true
    },
    closeSidePanel: (state) => {
      state.sidePanel.isSidePanelOpen = false
    },
    setSidePanelExploreParams: (state, action: PayloadAction<ExploreParams>) => {
      state.sidePanel.exploreParams = action.payload
    },
    clearHistory : (state) => {
      state.history = []
    },
    updateLastHistoryEntry: (state) => {
      if (state.currentExploreThread === null) {
        return
      }

      if (state.history.length === 0) {
        state.history.push({ ...state.currentExploreThread })
      } else {
        const currentUuid = state.currentExploreThread.uuid
        const lastHistoryUuid = state.history[state.history.length - 1].uuid
        if (currentUuid !== lastHistoryUuid) {
          state.history.push({ ...state.currentExploreThread })
        } else {
          state.history[state.history.length - 1] = { ...state.currentExploreThread }
        }
      }
    },
    setSemanticModels: (state, action: PayloadAction<AssistantState['semanticModels']>) => {
      state.semanticModels = action.payload
    },
    setExploreParams: (state, action: PayloadAction<ExploreParams>) => {
      if (state.currentExploreThread === null) {
        state.currentExploreThread = newThreadState()
      }
      state.currentExploreThread.exploreParams = action.payload
    },
    updateCurrentThread: (
      state,
      action: PayloadAction<Partial<ExploreThread>>,
    ) => {
      if (state.currentExploreThread === null) {
        state.currentExploreThread = newThreadState()
      }
      state.currentExploreThread = {
        ...state.currentExploreThread,
        ...action.payload,
      }
    },
    setCurrentThread: (state, action: PayloadAction<ExploreThread>) => {
      state.currentExploreThread = { ...action.payload }
    },
    setQuery: (state, action: PayloadAction<string>) => {
      state.query = action.payload
    },
    resetChat: (state) => {
      // Preserve the current explore context when resetting chat
      const currentExplore = state.currentExplore
      const newThread = newThreadState()
      newThread.uuid = uuidv4()
      
      // Set the new thread's explore info to match current explore
      if (currentExplore.exploreKey) {
        newThread.exploreKey = currentExplore.exploreKey
        newThread.exploreId = currentExplore.exploreId
        newThread.modelName = currentExplore.modelName
      }
      
      state.currentExploreThread = newThread
      state.query = ''
      state.isChatMode = false
      state.isQuerying = false
      state.sidePanel = initialState.sidePanel
    },
    addMessage: (state, action: PayloadAction<ChatMessage>) => {
      if (state.currentExploreThread === null) {
        state.currentExploreThread = newThreadState()
      }
      if (action.payload.uuid === undefined) {
        action.payload.uuid = uuidv4()
      }
      state.currentExploreThread.messages.push(action.payload)
    },
    setExploreGenerationExamples(
      state,
      action: PayloadAction<AssistantState['examples']['exploreGenerationExamples']>,
    ) {
      state.examples.exploreGenerationExamples = action.payload
    },
    setExploreRefinementExamples(
      state,
      action: PayloadAction<AssistantState['examples']['exploreRefinementExamples']>,
    ) {
      state.examples.exploreRefinementExamples = action.payload
    },
    updateSummaryMessage: (
      state,
      action: PayloadAction<{ uuid: string; summary: string }>,
    ) => {
      const { uuid, summary } = action.payload
      if (state.currentExploreThread === null) {
        state.currentExploreThread = newThreadState()
      }
      const message = state.currentExploreThread.messages.find(
        (message) => message.uuid === uuid,
      ) as SummarizeMesage
      if (message) {
        message.summary = summary
      }
    },
    setExploreSamples(
      state,
      action: PayloadAction<ExploreSamples>,
    ) {
      state.examples.exploreSamples = action.payload
    },
    setExploreEntries(
      state,
      action: PayloadAction<any[]>,
    ) {
      state.examples.exploreEntries = action.payload
    },
    setisBigQueryMetadataLoaded: (
      state, 
      action: PayloadAction<boolean>
    ) => {
      state.isBigQueryMetadataLoaded = action.payload
    },
    setIsSemanticModelLoaded: (state, action: PayloadAction<boolean>) => {
      state.isSemanticModelLoaded = action.payload
    },
    setCurrenExplore: (state, action: PayloadAction<AssistantState['currentExplore']>) => {
      state.currentExplore = action.payload
    },
    setBigQueryTestSuccessful: (state, action: PayloadAction<boolean>) => {
      state.bigQueryTestSuccessful = action.payload
    },
    setVertexTestSuccessful: (state, action: PayloadAction<boolean>) => {
      state.vertexTestSuccessful = action.payload
      state.testsSuccessful = state.bigQueryTestSuccessful && state.vertexTestSuccessful
    },
    setShowConnectionBanner: (state, action: PayloadAction<boolean>) => {
      state.showConnectionBanner = action.payload
    },
    // User attribute loading actions
    setUserAttributesLoaded: (state, action: PayloadAction<boolean>) => {
      state.userAttributesLoaded = action.payload
    },
    setInitialTestsCompleted: (state, action: PayloadAction<boolean>) => {
      state.initialTestsCompleted = action.payload
    },
    ensureValidExploreContext: (state) => {
      // If we don't have a valid explore context, try to set one from available samples
      if (!state.currentExplore.exploreKey || !state.currentExplore.modelName || !state.currentExplore.exploreId) {
        const availableExplores = Object.keys(state.examples.exploreSamples)
        if (availableExplores.length > 0) {
          // Could implement logic to set first explore here if needed
        }
      }
    },
    setAvailableAreas: (state, action: PayloadAction<Area[]>) => {
      state.availableAreas = action.payload
    },
    setSelectedArea: (state, action: PayloadAction<string | null>) => {
      state.selectedArea = action.payload
      // Clear selected explores when area changes
      state.selectedExplores = []
    },
    setSelectedExplores: (state, action: PayloadAction<string[]>) => {
      state.selectedExplores = action.payload
    },
    setIsAreasLoaded: (state, action: PayloadAction<boolean>) => {
      state.isAreasLoaded = action.payload
    },
  },
})

export const {
  setIsQuerying,
  setIsChatMode,
  resetChatMode,

  updateLastHistoryEntry,
  clearHistory,

  setSemanticModels,
  setIsSemanticModelLoaded,
  setExploreParams,
  setQuery,
  resetChat,
  addMessage,
  setExploreGenerationExamples,
  setExploreRefinementExamples,
  setExploreSamples,
  setExploreEntries,
  
  setisBigQueryMetadataLoaded,

  updateCurrentThread,
  setCurrentThread,

  openSidePanel,
  closeSidePanel,
  setSidePanelExploreParams,

  updateSummaryMessage,

  setCurrenExplore,

  resetExploreAssistant,
  setBigQueryTestSuccessful,
  setVertexTestSuccessful,
  setShowConnectionBanner,

  // User attribute loading actions
  setUserAttributesLoaded,
  setInitialTestsCompleted,
  ensureValidExploreContext,

  // Area selection actions
  setAvailableAreas,
  setSelectedArea,
  setSelectedExplores,
  setIsAreasLoaded,
} = assistantSlice.actions

export default assistantSlice.reducer
