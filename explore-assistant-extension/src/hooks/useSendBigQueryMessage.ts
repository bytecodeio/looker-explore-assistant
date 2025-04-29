import { ExtensionContext } from '@looker/extension-sdk-react'
import { useCallback, useContext } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { useErrorBoundary } from 'react-error-boundary'
import { AssistantState } from '../slices/assistantSlice'

import looker_filter_doc from '../documents/looker_filter_doc.md'
// import looker_visualization_doc from '../documents/looker_visualization_doc.md'
import looker_filters_interval_tf from '../documents/looker_filters_interval_tf'
import looker_pivots_url_parameters_doc from '../documents/looker_pivots_url_parameters_doc.md'

import { BigQueryParameters } from '../utils/BigQueryHelper'
import { ExploreParams } from '../slices/assistantSlice'
import { ExploreFilterValidator, FieldType } from '../utils/ExploreFilterHelper'


const parseJSONResponse = (jsonString: string | null | undefined) => {
  if (typeof jsonString !== 'string') {
    return {}
  }

  if (jsonString.startsWith('```json') && jsonString.endsWith('```')) {
    jsonString = jsonString.slice(7, -3).trim()
  }

  try {
    const parsed = JSON.parse(jsonString)
    return typeof parsed === 'object' ? parsed : {}
  } catch (error) {
    return {}
  }
}

function formatRow(field: {
  name?: string
  type?: string
  label?: string
  description?: string
  tags?: string[]
}) {
  // Initialize properties with default values if not provided
  const name = field.name || ''
  const type = field.type || ''
  const label = field.label || ''
  const description = field.description || ''
  const tags = field.tags ? field.tags.join(', ') : ''

  // Return a markdown row
  return `| ${name} | ${type} | ${label} | ${description} | ${tags} |`
}

const useSendBigQueryMessage = () => {
  const { showBoundary } = useErrorBoundary()

  const { core40SDK } = useContext(ExtensionContext)

  const { settings, examples, currentExplore } = useSelector(
    (state: RootState) => state.assistant as AssistantState,
  )
  const BIGQUERY_EXAMPLE_LOOKER_MODEL_NAME = settings['bigquery_example_looker_model_name']?.value || 'explore_assistant'

  const currentExploreKey = currentExplore.exploreKey
  const exploreRefinementExamples =
    examples.exploreRefinementExamples[currentExploreKey]

  // Get model name from settings directly without splitting/processing 
  const modelName = BIGQUERY_EXAMPLE_LOOKER_MODEL_NAME
  console.log('Using model name for LLM queries:', modelName)

  const sendViaBigQuery = async (
    contents: string,
    parameters: BigQueryParameters,
  ) => {
    try {     // Escape special characters
      const sanitizedContents = `"${contents
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, ' ') 
        .replace(/\r/g, ' ') 
        .replace(/\t/g, ' ') 
        .replace(/,/g, ' ')  }"`
      
      console.log(`Querying with model: ${modelName}, view: explore_assistant`)
      
      const queryBody = {
        model: modelName as string,
        view: "explore_assistant",
        filters: {
          'explore_assistant.prompt': sanitizedContents,
        },
        fields: [`explore_assistant.generated_content`],
      }
      
      console.log('Query body:', JSON.stringify(queryBody))
      
      const query = await core40SDK.ok(
        core40SDK.run_inline_query({
          result_format: 'json',
          body: queryBody
        })
      )

      if (query === undefined || query.length === 0) {
        console.error('Empty query result')
        return ''
      }
      
      // Extract the first result's generated content
      console.log('Got query result:', query[0])
      return query[0]['explore_assistant.generated_content'] || ''
    } catch (error: any) {
      if (error.name === 'LookerSDKError' || error.message === 'Model Not Found') {
        console.error(`Error running query: ${error.message}`, error)
        return 'Error: Could not access the LLM model. Please verify your model name in settings.'
      }
      showBoundary(error)
      throw new Error('error')
    }
  }

  const summarizePrompts = useCallback(
    async (promptList: string[]) => {
      const contents = `
    
      Primer
      ----------
      A user is iteractively asking questions to generate an explore URL in Looker. The user is refining his questions by adding more context. The additional prompts he is adding could have conflicting or duplicative information: in those cases, prefer the most recent prompt. 

      Here are some example prompts the user has asked so far and how to summarize them:

${exploreRefinementExamples &&
        exploreRefinementExamples
          .map((item) => {
            const inputText = '"' + item.input.join('", "') + '"'
            return `- The sequence of prompts from the user: ${inputText}. The summarized prompts: "${item.output}"`
          })
          .join('\n')
        }

      Conversation so far
      ----------
      input: ${promptList.map((prompt) => '"' + prompt + '"').join('\n')}
    
      Task
      ----------
      Summarize the prompts above to generate a single prompt that includes all the relevant information. If there are conflicting or duplicative information, prefer the most recent prompt.

      Only return the summary of the prompt with no extra explanatation or text
        
    `
      const response = await sendMessage(contents, {})

      return response
    },
    [exploreRefinementExamples],
  )

  const promptWrapper = (prompt: string) => {
    // wrap the prompt with the current date
    const currentDate = new Date().toLocaleString()
    return `The current date is ${currentDate}
    
    
    ${prompt}
    `
  }

  const generateSharedContext = (dimensions: any[], measures: any[], exploreGenerationExamples: any[]) => {
    if (!dimensions.length || !measures.length) {
      showBoundary(new Error('Dimensions or measures are not defined'))
      return
    }
    let exampleText = ''
    if (exploreGenerationExamples && exploreGenerationExamples.length > 0) {
      console.log("Line",exploreGenerationExamples)
      exampleText = exploreGenerationExamples.map((item) => `input: "${item.input}" ; output: ${JSON.stringify(parseLookerURL(item.output))}`).join('\n')
    }
    return `
      # Documentation
      Here is general documentation about filters:
        ${looker_filter_doc}
      Here is general documentation on how intervals and timeframes are applied in Looker
       ${looker_filters_interval_tf}   
      Here is general documentation on Looker JSON fields and pivots
       ${looker_pivots_url_parameters_doc}
             
      ## Format of query object
      
      | Field              | Type   | Description                                                                                                                                                                                                                                                                          |
      |--------------------|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
      | model              | string | Model                                                                                                                                                                                                                                                                                |
      | view               | string | Explore Name                                                                                                                                                                                                                                                                         |
      | fields             | string[] | Fields                                                                                                                                                                                                                                                                                |
      | pivots             | string[] | Pivots                                                                                                                                                                                                                                                                                |
      | fill_fields        | string[] | Fill Fields                                                                                                                                                                                                                                                                           |
      | filters            | object | Filters                                                                                                                                                                                                                                                                               |
      | filter_expression  | string | Filter Expression                                                                                                                                                                                                                                                                     |
      | sorts              | string[] | Sorts                                                                                                                                                                                                                                                                                 |
      | limit              | string | Limit                                                                                                                                                                                                                                                                                 |
      | column_limit       | string | Column Limit                                                                                                                                                                                                                                                                          |
      | total              | boolean | Total                                                                                                                                                                                                                                                                                 |
      | row_total          | string | Raw Total                                                                                                                                                                                                                                                                             |
      | subtotals          | string[] | Subtotals                                                                                                                                                                                                                                                                             |
      | vis_config         | object | Visualization configuration properties. These properties are typically opaque and differ based on the type of visualization used. There is no specified set of allowed keys. The values can be any type supported by JSON. A "type" key with a string value is often present, and is used by Looker to determine which visualization to present. Visualizations ignore unknown vis_config properties. |
      | filter_config      | object | The filter_config represents the state of the filter UI on the explore page for a given query. When running a query via the Looker UI, this parameter takes precedence over "filters". When creating a query or modifying an existing query, "filter_config" should be set to null. Setting it to any other value could cause unexpected filtering behavior. The format should be considered opaque. |
          
      # End Documentation
      
           
      # Metadata
      This information is particular to the current Looker instance and data model. The fields below can be used in the response.
      Model: ${currentExplore.modelName}
      Explore: ${currentExplore.exploreId}
      
      Dimensions Used to group by information (follow the instructions in tags when using a specific field; if map used include a location or lat long dimension;):
      
      | Field Id | Field Type | LookML Type | Label | Description | Tags |
      |------------|------------|-------------|-------|-------------|------|
      ${dimensions.map(formatRow).join('\n')}
                
      Measures are used to perform calculations (if top, bottom, total, sum, etc. are used include a measure):
      
      | Field Id | Field Type | LookML Type | Label | Description | Tags |
      |------------|------------|-------------|-------|-------------|------|
      ${measures.map(formatRow).join('\n')}
      # End LookML Metadata
    
      # Example 
        Examples Below include the fields, filters and sometimes visualization configs. 
        They were taken at a different date. ALL DATE RANGES ARE WRONG COMPARING TO CURRENT DATE.
        (BE CAREFUL WITH DATES, DO NOT OUTPUT THE Examples 1:1,  as changes could happen with timeframes and date ranges)
        ${exampleText}
      # End Examples
      
  `}

  const isSummarizationPrompt = async (prompt: string) => {
    const contents = `
      Primer
      ----------

      A user is interacting with an agent that is translating questions to a structured URL query based on the following dictionary. The user is refining his questions by adding more context. You are a very smart observer that will look at one such question and determine whether the user is asking for a data summary, or whether they are continuing to refine their question.
  
      Task
      ----------
      Determine if the user is asking for a data summary or continuing to refine their question. If they are asking for a summary, they might say things like:
      
      - summarize the data
      - give me the data
      - data summary
      - tell me more about it
      - explain to me what's going on
      
      The user said:

      ${prompt}

      Output
      ----------
      Return "data summary" if the user is asking for a data summary, and "refining question" if the user is continuing to refine their question. Only output one answer, no more. Only return one those two options. If you're not sure, return "refining question".

    `
    const response = await sendMessage(contents, {})
    return response === 'data summary'
  }

  const summarizeExplore = useCallback(
    async (exploreParams: ExploreParams) => {
      const filters: Record<string, string> = {}
      if (exploreParams.filters !== undefined) {
        const exploreFiltters = exploreParams.filters
        Object.keys(exploreFiltters).forEach((key: string) => {
          if (!exploreFiltters[key]) {
            return
          }
          const filter: string[] | string = exploreFiltters[key]
          if (typeof filter === 'string') {
            filters[key] = filter
          }
          if (Array.isArray(filter)) {
            filters[key] = filter.join(', ')
          }
        })
      }

      // get the contents of the explore query
      const createQuery = await core40SDK.ok(
        core40SDK.create_query({
          model: currentExplore.modelName,
          view: currentExplore.exploreId,

          fields: exploreParams.fields || [],
          filters: filters,
          sorts: exploreParams.sorts || [],
          limit: exploreParams.limit || '1000',
        }),
      )

      const queryId = createQuery.id
      if (queryId === undefined || queryId === null) {
        return 'There was an error creating query!!'
      }
      
      // Create an async query task instead of directly running the query
      const queryTask = await core40SDK.ok(
        core40SDK.create_query_task({
          query_id: queryId,
          result_format: 'md'
        })
      )
      
      if (!queryTask.id) {
        return 'There was an error creating query task!!'
      }
      
      // Poll the task status until it completes
      let taskComplete = false
      let taskStatus: any
      while (!taskComplete) {
        taskStatus = await core40SDK.ok(
          core40SDK.query_task(queryTask.id)
        )
        
        if (taskStatus.status === 'complete' || taskStatus.status === 'error') {
          taskComplete = true
        } else {
          // Wait a bit before polling again
          await new Promise(resolve => setTimeout(resolve, 400))
        }
      }
      
      if (taskStatus.status === 'error') {
        return 'There was an error running the query!!'
      }
      
      // Get the results from the completed task
      const result = await core40SDK.ok(
        core40SDK.query_task_results(queryTask.id)
      )

      if (!result || result.length === 0) {
        return 'There was an error retrieving query results!!'
      }

      const contents = `
      Data
      ----------

      ${result}
      
      Task
      ----------
      Summarize the data above
    
    `
      const response = await sendMessage(contents, {})

      const refinedContents = `
      The following text represents summaries of a given dashboard's data. 
        Summaries: ${response}

        Make this much more concise for a slide presentation using the following format. The summary should be a markdown documents that contains a list of sections, each section should have the following details:  a section title, which is the title for the given part of the summary, and key points which a list of key points for the concise summary. Data should be returned in each section, you will be penalized if it doesn't adhere to this format. Each summary should only be included once. Do not include the same summary twice.
        `

      const refinedResponse = await sendMessage(refinedContents, {})
      return refinedResponse
    },
    [currentExplore],
  )
  
  const parseLookerURL = (url: string): { [key: string]: any } => {
    // Split URL and extract model & explore
    const urlSplit = url.split("?");
    let model = ""
    let explore = ""
    let queryString = ""
    if (urlSplit.length == 2) {
      const rootURL = urlSplit[0]
      queryString = urlSplit[1]
      const rootURLElements = rootURL.split("/");
      model = rootURLElements[rootURLElements.length - 2];
      explore = rootURLElements[rootURLElements.length - 1];
    }
    else if (urlSplit.length == 1) {
      model = "tbd"
      explore = "tbd"
      queryString = urlSplit[0]
    }
    // Initialize lookerEncoding object
    const lookerEncoding: { [key: string]: any } = {};
    lookerEncoding['model'] = ""
    lookerEncoding['explore'] = ""
    lookerEncoding['fields'] = []
    lookerEncoding['pivots'] = []
    lookerEncoding['fill_fields'] = []
    lookerEncoding['filters'] = {}
    lookerEncoding['filter_expression'] = null
    lookerEncoding['sorts'] = []
    lookerEncoding['limit'] = 500
    lookerEncoding['column_limit'] = 50
    lookerEncoding['total'] = null
    lookerEncoding['row_total'] = null
    lookerEncoding['subtotals'] = null
    lookerEncoding['vis'] = []
    // Split query string and iterate key-value pairs
    const keyValuePairs = queryString.split("&");
    for (const qq of keyValuePairs) {
      const [key, value] = qq.split('=');
      console.log(qq)
      lookerEncoding['model'] = model
      lookerEncoding['explore'] = explore
      switch (key) {
        case "fields":
        case "pivots":
        case "fill_fields":
        case "sorts":
          lookerEncoding[key] = value.split(",");
          break;
        case "filter_expression":
        case "total":
        case "row_total":
        case "subtotals":
          lookerEncoding[key] = value;
          break;
        case "limit":
        case "column_limit":
          lookerEncoding[key] = parseInt(value);
          break;
        case "vis":
          lookerEncoding[key] = JSON.parse(decodeURIComponent(value));
          break;
        default:
          if (key.startsWith("f[")) {
            const filterKey = key.slice(2, -1);
            lookerEncoding.filters[filterKey] = value;
          } else if (key.includes(".")) {
            const path = key.split(".");
            let currentObject = lookerEncoding;
            for (let i = 0; i < path.length - 1; i++) {
              const segment = path[i];
              if (!currentObject[segment]) {
                currentObject[segment] = {};
              }
              currentObject = currentObject[segment];
            }
            currentObject[path[path.length - 1]] = value;
          }
      }
    }
    return lookerEncoding;
  };
  const validateFilters = useCallback(
    (filterResponseJSON: any, dimensions: any[], measures: any[]) => {
      const validatedFilters: any = {}
      
      // If filters is not an object, return empty object
      if (!filterResponseJSON || typeof filterResponseJSON !== 'object') {
        return validatedFilters
      }
      
      // Iterate through each filter
      Object.entries(filterResponseJSON).forEach(([fieldId, expression]) => {
        const field = dimensions.find((d) => d.name === fieldId) ||
                     measures.find((m) => m.name === fieldId)

        if (!field) {
          console.log(`Invalid field: ${fieldId}`)
          return
        }

        console.log(field)
        
        // Handle both string and array expressions
        const expressions = Array.isArray(expression) ? expression : [expression]
        const validExpressions = []
        
        for (const expr of expressions) {
          const isValid = ExploreFilterValidator.isFilterValid(
            field.type as FieldType,
            expr
          )

          if (isValid) {
            validExpressions.push(expr)
          } else {
            console.log(
              `Invalid filter expression for field ${fieldId}: ${expr}`
            )
          }
        }
        
        if (validExpressions.length > 0) {
          validatedFilters[fieldId] = validExpressions.length === 1 ? 
            validExpressions[0] : validExpressions
        }
      })

      return validatedFilters
    },
    []
  )

  const generateBaseExploreParams = useCallback(
    async (
      prompt: string,
      sharedContext,
    ) => {
      const currentDateTime = new Date().toISOString()

      const contents = `
      ${sharedContext}
      
      Output
      ----------
      
      Return a JSON that is compatible with the Looker API run_inline_query function as per the spec. Here is an example:
      
      {
        "model":"${currentExplore.modelName}",
        "view":"${currentExplore.exploreId}",
        "fields":["category.name","inventory_items.days_in_inventory_tier","products.count"],
        "filters":{"category.name":"socks"},
        "sorts":["products.count desc 0"],
        "limit":"500",
      }
      
      Instructions:
      - choose only the fields in the below lookml metadata
      - prioritize the field description, label, tags, and name for what field(s) to use for a given description
      - generate only one answer, no more.
      - use the Examples for guidance on how to structure the body
      - try to avoid adding dynamic_fields, provide them when very similar example is found in the bottom
      - Always use the provided current date (${currentDateTime}) when generating Looker URL queries that involve TIMEFRAMES.
      - For filters, verify that you're only using valid expressions for the filter values.
      - For filters, verify that the field ids are indeed Field Ids from the metadata tables. There should be a period in the field id.
      - only respond with a JSON object
        
      User Request
      ----------
      ${prompt}
      
      `

      const parameters = {
        max_output_tokens: 1000,
      }
      console.log(contents)
      const response = await sendMessage(contents, parameters)
      const responseJSON = parseJSONResponse(response)

      return responseJSON
    },
    [currentExplore],
  )

  const generateExploreParams = useCallback(
    async (
      prompt: string,
      dimensions: any[],
      measures: any[],
      exploreGenerationExamples: any[],
    ) => {
      if (!dimensions.length || !measures.length) {
        showBoundary(new Error('Dimensions or measures are not defined'))
        return
      }
      const sharedContext = generateSharedContext(dimensions, measures, exploreGenerationExamples) || ''
      
      // Make a single call to get all explore parameters including filters
      const responseJSON = await generateBaseExploreParams(prompt, sharedContext)
      
      // Extract and validate the filters that were included in the response
      const validatedFilters = validateFilters(responseJSON.filters, dimensions, measures)
      
      // Update the filters in the response with the validated filters
      responseJSON.filters = validatedFilters

      return responseJSON
    },
    [settings],
  )

  const generateVisualizationParams = async (
    exploreParams: ExploreParams,
    prompt: string,
  ) => {
    const contents = `

    ${looker_visualization_doc}

      # User Request

      ## Prompt

      The user asked the following question:

      \`\`\`
      ${prompt}
      \`\`\`

      ## Explore Definition

      The user is asking for the following explore definition:

      \`\`\`
      ${JSON.stringify(exploreParams)}
      \`\`\`

      ## Determine Visualization JSON

      Based on the question, and on the original question, determine what the visualization config should be. The visualization config should be a JSON object that is compatible with the Looker API run_inline_query function. Only contain values that are different than the defaults. Here is an example:

      \`\`\`
      {
        "type": "looker_column",
      }
      \`\`\`

    `
    const parameters = {
      max_output_tokens: 1000,
    }
    const response = await sendMessage(contents, parameters)
    return parseJSONResponse(response)
  }

  const sendMessage = async (message: string, parameters: BigQueryParameters) => {
    const wrappedMessage = promptWrapper(message)
    try {
      const response = await sendViaBigQuery(wrappedMessage, parameters)
      return response
    } catch (error) {
      showBoundary(error)
      return ''
    }
  }

  return {
    generateExploreParams,
    generateBaseExploreParams,
    generateVisualizationParams,
    sendMessage,
    summarizePrompts,
    isSummarizationPrompt,
    summarizeExplore,
  }
}

export default useSendBigQueryMessage
