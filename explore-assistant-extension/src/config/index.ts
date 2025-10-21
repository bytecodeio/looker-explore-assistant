/**
 * Configuration module for Looker Explore Assistant
 * 
 * This module provides typed access to environment variables that are injected
 * at build time via webpack. Settings are no longer user-configurable and are
 * compiled into the extension based on .env variables.
 */

declare const process: {
  env: {
    [key: string]: string | undefined;
  };
};

export interface AppConfig {
  // Vertex AI Configuration
  vertexAiEndpoint: string;
  vertexCfAuthToken: string;
  vertexModel: string;
  
  // BigQuery Configuration
  bigqueryExamplePromptsConnectionName: string;
  bigqueryExamplePromptsDatasetName: string;
  bigqueryExampleLookerModelName: string;
  vertexBigqueryLookerConnectionName: string;
  vertexBigqueryModelId: string;
  
  // Cloud Run Configuration
  cloudRunServiceUrl: string;
  
  // API Key Authentication
  apiKey: string;
  
  // UI Configuration
  showExploreData: boolean;
  showConnectionBanner: boolean;
}

/**
 * Default configuration values
 */
const DEFAULT_CONFIG: AppConfig = {
  // Vertex AI Configuration
  vertexAiEndpoint: '',
  vertexCfAuthToken: '',
  vertexModel: 'gemini-2.0-flash',
  
  // BigQuery Configuration
  bigqueryExamplePromptsConnectionName: '',
  bigqueryExamplePromptsDatasetName: '',
  bigqueryExampleLookerModelName: 'extension_apps',
  vertexBigqueryLookerConnectionName: '',
  vertexBigqueryModelId: '',
  
  // Cloud Run Configuration
  cloudRunServiceUrl: '',
  
  // API Key Authentication
  apiKey: '',
  
  // UI Configuration
  showExploreData: false,
  showConnectionBanner: true,
};

/**
 * Parse boolean from string environment variable
 */
function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (!value) return defaultValue;
  return value.toLowerCase() === 'true';
}

/**
 * Get configuration value from environment with fallback to default
 */
function getEnvValue(key: string, defaultValue: string): string {
  return process.env[key] || defaultValue;
}

/**
 * Application configuration loaded from environment variables at build time
 */
export const appConfig: AppConfig = {
  // Vertex AI Configuration
  vertexAiEndpoint: getEnvValue('VERTEX_AI_ENDPOINT', DEFAULT_CONFIG.vertexAiEndpoint),
  vertexCfAuthToken: getEnvValue('VERTEX_CF_AUTH_TOKEN', DEFAULT_CONFIG.vertexCfAuthToken),
  vertexModel: getEnvValue('VERTEX_MODEL', DEFAULT_CONFIG.vertexModel),
  
  // BigQuery Configuration
  bigqueryExamplePromptsConnectionName: getEnvValue('BIGQUERY_EXAMPLE_PROMPTS_CONNECTION_NAME', DEFAULT_CONFIG.bigqueryExamplePromptsConnectionName),
  bigqueryExamplePromptsDatasetName: getEnvValue('BIGQUERY_EXAMPLE_PROMPTS_DATASET_NAME', DEFAULT_CONFIG.bigqueryExamplePromptsDatasetName),
  bigqueryExampleLookerModelName: getEnvValue('BIGQUERY_EXAMPLE_LOOKER_MODEL_NAME', DEFAULT_CONFIG.bigqueryExampleLookerModelName),
  vertexBigqueryLookerConnectionName: getEnvValue('VERTEX_BIGQUERY_LOOKER_CONNECTION_NAME', DEFAULT_CONFIG.vertexBigqueryLookerConnectionName),
  vertexBigqueryModelId: getEnvValue('VERTEX_BIGQUERY_MODEL_ID', DEFAULT_CONFIG.vertexBigqueryModelId),
  
  // Cloud Run Configuration
  cloudRunServiceUrl: getEnvValue('CLOUD_RUN_SERVICE_URL', DEFAULT_CONFIG.cloudRunServiceUrl),
  
  // API Key Authentication
  apiKey: getEnvValue('API_KEY', DEFAULT_CONFIG.apiKey),
  
  // UI Configuration
  showExploreData: parseBoolean(process.env.SHOW_EXPLORE_DATA, DEFAULT_CONFIG.showExploreData),
  showConnectionBanner: parseBoolean(process.env.SHOW_CONNECTION_BANNER, DEFAULT_CONFIG.showConnectionBanner),
};

/**
 * Validate that required configuration values are present
 */
export function validateConfig(): string[] {
  const errors: string[] = [];
  
  if (!appConfig.cloudRunServiceUrl) {
    errors.push('CLOUD_RUN_SERVICE_URL is required');
  }
  
  if (!appConfig.apiKey) {
    errors.push('API_KEY is required');
  }
  
  if (!appConfig.bigqueryExamplePromptsConnectionName) {
    errors.push('BIGQUERY_EXAMPLE_PROMPTS_CONNECTION_NAME is required');
  }
  
  if (!appConfig.bigqueryExampleLookerModelName) {
    errors.push('BIGQUERY_EXAMPLE_LOOKER_MODEL_NAME is required');
  }
  
  return errors;
}

export default appConfig;