import { useCallback, useContext } from 'react'
import { useSelector } from 'react-redux'
import { ExtensionContext } from '@looker/extension-sdk-react'
import { RootState } from '../store'
import { AssistantState } from '../slices/assistantSlice'

const useConversationalAnalytics = () => {
  const { lookerHostData, core40SDK } = useContext(ExtensionContext)
  
  const { settings, currentExplore } = useSelector(
    (state: RootState) => state.assistant as AssistantState,
  )
  
  // Get required settings
  const VERTEX_PROJECT = settings['vertex_project']?.value as string || ''
  const VERTEX_LOCATION = 'us-central1'
  const oauth2Token = settings['oauth2_token']?.value as string || ''
  
  // Get Looker instance URI from the extension context
  const lookerInstanceUri = lookerHostData?.hostUrl || ''

  // Function to get the user-specific OAuth token via Looker SDK
  const getLookerUserToken = useCallback(async (): Promise<string | null> => {
    try {
      // Get current user ID
      const currentUser = await core40SDK.ok(core40SDK.me())
      const userId = currentUser.id
      
      if (!userId) {
        throw new Error('Unable to get current user ID')
      }
      
      console.log('Getting login token for user ID:', userId)
      
      // Call login_user to get the user-specific OAuth token
      const loginResponse = await core40SDK.ok(core40SDK.login_user(userId))
      
      if (loginResponse.access_token) {
        console.log('Successfully obtained user login token')
        return loginResponse.access_token
      } else {
        throw new Error('No access token returned from login_user')
      }
    } catch (error) {
      console.error('Error getting Looker user token:', error)
      return null
    }
  }, [core40SDK])

  const callConversationalAnalyticsAPI = useCallback(async (
    prompt: string,
    systemInstruction?: string
  ) => {
    try {
      console.log('Calling ConversationalAnalytics API with prompt length:', prompt.length);
      
      if (!VERTEX_PROJECT) {
        throw new Error('Vertex project is required but not provided');
      }

      if (!lookerInstanceUri) {
        throw new Error('Looker instance URI is required but not provided');
      }

      // Get the user-specific OAuth token via Looker SDK
      const userToken = await getLookerUserToken()
      if (!userToken) {
        throw new Error('Failed to obtain user OAuth token from Looker')
      }

      const requestBody = {
        project: VERTEX_PROJECT,
        messages: [
          {
            user_message: {
              text: prompt,
            },
          },
        ],
        inlineContext: {
          system_instruction: systemInstruction || "You are a helpful data analyst assistant. Generate valid JSON responses for Looker queries.",
          datasource_references: {
            looker: {
              explore_references: [
                {
                  looker_instance_uri: lookerInstanceUri,
                  lookml_model: currentExplore.modelName,
                  explore: currentExplore.exploreId,
                },
              ],
              credentials: {
                oauth: {
                  token: {
                    access_token: userToken,
                  },
                },
              },
            },
          },
        },
      };

      const endpoint = `https://geminidataanalytics.googleapis.com/v1alpha/projects/${VERTEX_PROJECT}/locations/${VERTEX_LOCATION}:chat`;
      
      console.log(`Making ConversationalAnalytics request to: ${endpoint}`);
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${oauth2Token}`
        },
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('ConversationalAnalytics API call failed:', errorText);
        throw new Error(`ConversationalAnalytics API call failed: ${response.status} - ${errorText}`);
      }
      
      const responseData = await response.json();
      console.log('ConversationalAnalytics API call successful, response:', responseData);
      
      // Return the full response data so we can extract both text and query data
      return responseData;
    } catch (error) {
      console.error('Error calling ConversationalAnalytics API:', error);
      throw error;
    }
  }, [VERTEX_PROJECT, VERTEX_LOCATION, lookerInstanceUri, currentExplore.modelName, currentExplore.exploreId, oauth2Token, getLookerUserToken])

  const generateBaseExploreParams = useCallback(
    async (prompt: string, goldenQueries: any[]) => {
      const currentDateTime = new Date().toISOString();

      // Format golden queries for the system instruction
      let goldenQueriesText = '';
      if (goldenQueries && goldenQueries.length > 0) {
        goldenQueriesText = goldenQueries.map((item, index) => {
          return `Example ${index + 1}:
Input: "${item.input}"
Output: ${item.output}
`;
        }).join('\n');
      }

      // Create system instruction with golden queries
      const systemInstruction = `
You are a Looker data analyst assistant. Generate JSON responses compatible with the Looker API run_inline_query function.

Model: ${currentExplore.modelName}
Explore: ${currentExplore.exploreId}

Golden Query Examples:
${goldenQueriesText}

Instructions:
- Generate a JSON query similar to the golden query examples above
- Use the same model and explore: "${currentExplore.modelName}" and "${currentExplore.exploreId}"
- Generate only one JSON response
- Always use the current date (${currentDateTime}) for timeframe queries
- Only respond with a valid JSON object in this format:

{
  "model":"${currentExplore.modelName}",
  "view":"${currentExplore.exploreId}",
  "fields":["field1","field2"],
  "filters":{"field":"value"},
  "sorts":["field desc"],
  "limit":"500"
}
`;

      try {
        const startTime = Date.now();
        const response = await callConversationalAnalyticsAPI(prompt, systemInstruction);
        const endTime = Date.now();
        
        console.log(`ConversationalAnalytics generateBaseExploreParams completed in ${endTime - startTime}ms`);
        console.log('ConversationalAnalytics raw response:', response);

        // Parse the ConversationalAnalytics response format
        let exploreParams: any = {};
        let assistantMessages: string[] = [];
        
        // The API returns an array of messages, we need to find the ones with the data we need
        if (Array.isArray(response)) {
          // Look for systemMessage.data.generatedLookerQuery
          const queryMessage = response.find((msg: any) => 
            msg.systemMessage && 
            msg.systemMessage.data && 
            msg.systemMessage.data.generatedLookerQuery
          );
          
          if (queryMessage) {
            exploreParams = queryMessage.systemMessage.data.generatedLookerQuery;
            console.log('ConversationalAnalytics: Found generatedLookerQuery', exploreParams);
          }
          
          // Look for ALL systemMessage.text.parts (multiple messages possible)
          const textMessages = response.filter((msg: any) => 
            msg.systemMessage && 
            msg.systemMessage.text && 
            msg.systemMessage.text.parts && 
            msg.systemMessage.text.parts.length > 0
          );
          
          if (textMessages.length > 0) {
            textMessages.forEach((textMessage: any, index: number) => {
              const messageText = textMessage.systemMessage.text.parts.join(' ');
              if (messageText.trim()) {
                assistantMessages.push(messageText);
                console.log(`ConversationalAnalytics: Found assistant message ${index + 1}:`, messageText);
              }
            });
          }
        } else if ((response as any).systemMessage) {
          // Handle single message format
          const respObj = response as any;
          if (respObj.systemMessage.data && respObj.systemMessage.data.generatedLookerQuery) {
            exploreParams = respObj.systemMessage.data.generatedLookerQuery;
          }
          
          if (respObj.systemMessage.text && respObj.systemMessage.text.parts) {
            const messageText = respObj.systemMessage.text.parts.join(' ');
            if (messageText.trim()) {
              assistantMessages.push(messageText);
            }
          }
        }

        // Transform the filters format if needed (from array to object)
        if (exploreParams.filters && Array.isArray(exploreParams.filters)) {
          const filtersObject: { [key: string]: any } = {};
          exploreParams.filters.forEach((filter: any) => {
            if (filter.field && filter.value) {
              filtersObject[filter.field] = filter.value;
            }
          });
          exploreParams.filters = filtersObject;
        }

        // Log for comparison with existing implementation
        console.log('ConversationalAnalytics generateBaseExploreParams result:', {
          prompt: prompt.substring(0, 100) + '...',
          responseTime: endTime - startTime,
          hasValidQuery: Object.keys(exploreParams).length > 0,
          hasAssistantMessages: assistantMessages.length > 0,
          exploreParams: exploreParams,
          assistantMessages: assistantMessages
        });

        // Return both the explore parameters and the assistant messages
        return {
          exploreParams,
          assistantMessages,
          fullResponse: response
        };
      } catch (error) {
        console.error('ConversationalAnalytics generateBaseExploreParams error:', error);
        return {
          exploreParams: {},
          assistantMessages: [],
          fullResponse: null
        };
      }
    },
    [currentExplore, callConversationalAnalyticsAPI],
  );

  // Main function that matches the existing generateExploreParams interface
  const generateExploreParams = useCallback(
    async (
      prompt: string,
      dimensions: any[],
      measures: any[],
      exploreKey: string,
    ) => {
      // We'll get the golden queries from the examples, but for now use empty array
      const goldenQueries: any[] = [];
      
      console.log('ConversationalAnalytics generateExploreParams called with:', {
        promptLength: prompt.length,
        dimensionsCount: dimensions.length,
        measuresCount: measures.length,
        exploreKey,
        goldenQueriesCount: goldenQueries.length
      });

      const result = await generateBaseExploreParams(prompt, goldenQueries);
      
      // Return just the exploreParams to match the existing interface
      return result.exploreParams;
    },
    [generateBaseExploreParams],
  );

  return {
    generateBaseExploreParams,
    generateExploreParams,
    callConversationalAnalyticsAPI,
    getLookerUserToken
  };
};

export default useConversationalAnalytics;
