import { UtilsHelper } from "./Helper"

// Simple parameter interface to replace VertexHelper dependency
export interface BigQueryParameters {
  max_output_tokens?: number;
  temperature?: number;
  top_p?: number;
  top_k?: number;
}

export class BigQueryHelper {
  static getPromptQuery = (prompt: string) => {
    const escapedPrompt = UtilsHelper.escapeQueryAll(prompt)
    return `SELECT '` + escapedPrompt + `' AS prompt`
  }
}
