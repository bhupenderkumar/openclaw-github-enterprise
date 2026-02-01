// Test pi-ai SDK streaming directly
import { streamOpenAICompletions } from '@mariozechner/pi-ai';

async function test() {
  console.log('Testing pi-ai SDK with proxy...');
  
  const model = {
    api: 'openai-completions',
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'github-proxy',
    baseUrl: 'http://127.0.0.1:8000/v1',
    reasoning: false,
    input: ['text'],
    contextWindow: 128000,
    maxTokens: 16384,
  };

  const context = {
    messages: [
      { role: 'user', content: 'Say hi' }
    ]
  };

  try {
    const stream = streamOpenAICompletions(model, context, { apiKey: 'test' });
    
    for await (const event of stream) {
      console.log('Event:', event.type, JSON.stringify(event).slice(0, 200));
    }
    
    console.log('SUCCESS!');
  } catch (error) {
    console.error('Error:', error);
  }
}

test();
