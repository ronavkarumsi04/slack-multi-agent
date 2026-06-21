import { LLMProvider } from './provider';
import { getLogger } from '../../utils/logger';

const logger = getLogger('nim-provider');

export class NIMProvider implements LLMProvider {
  name = 'nim';
  private apiKey: string;
  private baseUrl = 'https://integrate.api.nvidia.com/v1';

  constructor() {
    this.apiKey = process.env.NIM_API_KEY!;
    if (!this.apiKey) {
      throw new Error('NIM_API_KEY not set');
    }
  }

  async complete(messages: Array<{ role: string; content: string }>, model: string, options?: { temperature?: number; maxTokens?: number }): Promise<string> {
    const response = await fetch(`${this.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: options?.temperature ?? 0.7,
        max_tokens: options?.maxTokens ?? 2000,
        stream: false
      })
    });

    if (!response.ok) {
      const error = await response.text();
      logger.error('NIM API error', { status: response.status, error });
      throw new Error(`NIM API error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return data.choices[0]?.message?.content || '';
  }

  async listModels(): Promise<string[]> {
    // NIM doesn't have a standard list models endpoint, return known models
    return [
      'meta/llama-3.1-70b-instruct',
      'meta/llama-3.1-8b-instruct',
      'mistralai/mixtral-8x7b-instruct-v0.1',
      'nvidia/nemotron-3-ultra',
      'google/gemma-2-27b-it'
    ];
  }
}
