import { renderHook, act } from '@testing-library/react-hooks'
import { useExploreSelection } from './useExploreSelection'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { Provider } from 'react-redux'
import { store } from '../store'
import React from 'react'

// Mock the Looker SDK
const mockCore40SDK = {
  ok: jest.fn(),
  run_inline_query: jest.fn(),
}

const mockExtensionSDK = {
  lookerHostData: {
    getCurrentUser: jest.fn().mockResolvedValue({ id: '123' }),
  }
}

// Mock context provider
jest.mock('@looker/extension-sdk-react', () => ({
  ExtensionContext: {
    Provider: ({ children }: { children: any }) => children,
    Consumer: ({ children }: { children: any }) => children({ 
      core40SDK: mockCore40SDK,
      extensionSDK: mockExtensionSDK
    }),
  }
}))

describe('useExploreSelection', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    
    // Mock successful response for table creation
    mockCore40SDK.ok.mockImplementation((promise) => {
      if (promise === mockCore40SDK.run_inline_query({
        result_format: 'json',
        body: {
          model: 'explore_assistant',
          view: "explore_selection_create",
          fields: ["explore_selection_create.creation_status"]
        }
      })) {
        return Promise.resolve([{ "explore_selection_create.creation_status": "Table Created Successfully" }])
      }
      
      return Promise.resolve([])
    })
  })
  
  it('should ensure table exists correctly', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <Provider store={store}>
        {/* @ts-ignore */}
        <ExtensionContext.Consumer>
          {(value) => children}
        </ExtensionContext.Consumer>
      </Provider>
    )
    
    const { result, waitForNextUpdate } = renderHook(() => useExploreSelection(), { wrapper })
    
    // Call the function
    let ensureTableResult: any
    
    act(() => {
      ensureTableResult = result.current.ensureExploreSelectionTable()
    })
    
    await waitForNextUpdate()
    
    // Verify the SDK was called correctly
    expect(mockCore40SDK.run_inline_query).toHaveBeenCalledWith({
      result_format: 'json',
      body: {
        model: 'explore_assistant',
        view: "explore_selection_create",
        fields: ["explore_selection_create.creation_status"]
      }
    })
    
    // Verify the result
    expect(ensureTableResult).resolves.toEqual({
      success: true,
      result: [{ "explore_selection_create.creation_status": "Table Created Successfully" }]
    })
  })
})