import { NIMProvider } from './nim';
import { GroqFallbackProvider } from './fallback';
import { LLMProvider } from './provider';
import { getConfig } from '../../storage/config';
import { getLogger } from '../../utils/logger';

const logger = getLogger('llm-router');

let nimProvider: NIMProvider | null = null;
let fallbackProvider: GroqFallbackProvider | null = null;

function getNIMProvider(): NIMProvider {
  if (!nimProvider) nimProvider = new NIMProvider();
  return nimProvider;
}

function getFallbackProvider(): GroqFallbackProvider {
  if (!fallbackProvider) fallbackProvider = new GroqFallbackProvider();
  return fallbackProvider;
}

export async function getLLMResponse(teamId: string, messages: Array<{ role: string; content: string }>, options?: { temperature?: number; maxTokens?: number }): Promise<string> {
  const config = await getConfig(teamId);
  const modelSpec = config.currentModel || 'nim:meta/llama-3.1-70b-instruct';

  let provider: LLMProvider;
  let model: string;

  if (modelSpec.startsWith('nim:')) {
    provider = getNIMProvider();
    model = modelSpec.slice(4);
  } else if (modelSpec.startsWith('fallback:')) {
    provider = getFallbackProvider();
    model = modelSpec.slice(9);
  } else {
    // Default to NIM
    provider = getNIMProvider();
    model = 'meta/llama-3.1-70b-instruct';
  }

  try {
    return await provider.complete(messages, model, options);
  } catch (error) {
    logger.warn('Primary provider failed, trying fallback', { primary: provider.name, error: error.message });
    
    // Try fallback if primary was NIM
    if (provider.name === 'nim') {
      try {
        const fallback = getFallbackProvider();
        return await fallback.complete(messages, 'llama-3.1-70b-versatile', options);
      } catch (fallbackError) {
        logger.error('Fallback also failed', { error: fallbackError.message });
        throw new Error('Both NIM and fallback providers failed');
      }
    }
    throw error;
  }
}

export async function getCurrentModelInfo(teamId: string): Promise<{ provider: string; model: string }> {
  const config = await getConfig(teamId);
  const modelSpec = config.currentModel || 'nim:meta/llama-3.1-70b-instruct';
  
  if (modelSpec.startsWith('nim:')) {
    return { provider: 'NVIDIA NIM', model: modelSpec.slice(4) };
  } else {
    return { provider: 'Groq (Fallback)', model: modelSpec.slice(9) };
  }
}
