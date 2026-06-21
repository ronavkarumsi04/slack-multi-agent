import { LLMProvider } from './provider';
import { getLogger } from '../../utils/logger';

const logger = getLogger('fallback-provider');

export class GroqFallbackProvider implements LLMProvider {
  name = 'fallback';
  private apiKey: string;
  private baseUrl = 'https://api.groq.com/openai/v1';

  constructor() {
    this.apiKey = process.env.GROQ_API_KEY!;
    if (!this.apiKey) {
      throw new Error('GROQ_API_KEY not set for fallback');
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
      logger.error('Groq API error', { status: response.status, error });
      throw new Error(`Groq API error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return data.choices[0]?.message?.content || '';
  }

  async listModels(): Promise<string[]> {
    return ['llama-3.1-70b-versatile', 'mixtral-8x7b-32768', 'gemma2-9b-it'];
  }
}
