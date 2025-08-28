import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { SSEClientTransport } from '@modelcontextprotocol/sdk/client/sse.js';
import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';

dotenv.config();

class RemoteMCPClient {
  constructor() {
    this.client = null;
    this.transport = null;
    this.gemini = new GoogleGenAI({
      apiKey: process.env.GOOGLE_API_KEY
    });
  }

  /**
   * Connect to a remote MCP server via SSE
   */
  async connectToRemoteServer(serverUrl, authHeaders = {}) {
    try {
      // Create SSE transport with authentication headers
      this.transport = new SSEClientTransport(serverUrl, {
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders
        }
      });

      // Initialize MCP client
      this.client = new Client(
        {
          name: 'gemini-mcp-client',
          version: '1.0.0'
        },
        {
          capabilities: {
            tools: {}
          }
        }
      );

      await this.client.connect(this.transport);
      console.log('✅ Connected to remote MCP server');
      return true;
    } catch (error) {
      console.error('❌ Connection failed:', error.message);
      throw error;
    }
  }

  /**
   * Process query using Gemini 2.5 Flash with remote MCP tools
   */
  async processQueryWithGemini(query) {
    if (!this.client) {
      throw new Error('Client not connected to server');
    }

    try {
      // Get available tools from remote server
      const toolsResponse = await this.client.listTools();
      const availableTools = toolsResponse.tools;

      // Prepare tools for Gemini
      const geminiTools = availableTools.map(tool => ({
        name: tool.name,
        description: tool.description,
        parameters: tool.inputSchema
      }));

      // Generate initial response with Gemini
      const response = await this.gemini.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: [{
          role: 'user',
          parts: [{
            text: `User query: ${query}\n\nAvailable tools: ${JSON.stringify(geminiTools, null, 2)}`
          }]
        }],
        tools: geminiTools,
        toolConfig: {
          functionCallingConfig: {
            mode: 'AUTO'
          }
        }
      });

      // Handle tool calls
      const content = response.candidates[0].content;
      let finalResponse = '';

      for (const part of content.parts) {
        if (part.text) {
          finalResponse += part.text;
        } else if (part.functionCall) {
          // Execute tool call on remote server
          const toolResult = await this.client.callTool({
            name: part.functionCall.name,
            arguments: part.functionCall.args
          });

          // Send tool result back to Gemini
          const followUpResponse = await this.gemini.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: [{
              role: 'user',
              parts: [{
                text: `Tool execution result for ${part.functionCall.name}: ${JSON.stringify(toolResult.content)}`
              }]
            }]
          });

          finalResponse += followUpResponse.candidates[0].content.parts[0].text;
        }
      }

      return finalResponse;

    } catch (error) {
      console.error('Error processing query:', error);
      throw error;
    }
  }

  /**
   * Interactive chat interface
   */
  async startChat() {
    const readline = require('readline').createInterface({
      input: process.stdin,
      output: process.stdout
    });

    console.log('\n🚀 MCP Client with Gemini 2.5 Flash Ready!');
    console.log('💡 Type your queries or "exit" to quit\n');

    const askQuestion = () => {
      readline.question('👤 You: ', async (query) => {
        if (query.toLowerCase() === 'exit') {
          readline.close();
          await this.disconnect();
          return;
        }

        try {
          const response = await this.processQueryWithGemini(query);
          console.log(`\n🤖 Assistant: ${response}\n`);
        } catch (error) {
          console.error('❌ Error:', error.message);
        }
        
        askQuestion();
      });
    };
    
    askQuestion();
  }

  /**
   * Cleanup connections
   */
  async disconnect() {
    if (this.transport) {
      await this.transport.close();
    }
    console.log('👋 Disconnected from server');
  }
}

// Example usage with different remote servers
async function main() {
  const client = new RemoteMCPClient();

  // Example 1: Connect to a public weather MCP server (hypothetical)
  const weatherServerConfig = {
    url: 'https://weather-mcp.example.com/sse',
    auth: {
      'Authorization': `Bearer ${process.env.WEATHER_API_KEY}`
    }
  };

  // Example 2: Connect to a cryptocurrency MCP server
  const cryptoServerConfig = {
    url: 'https://crypto-mcp.example.com/mcp',
    auth: {
      'X-API-Key': process.env.CRYPTO_API_KEY
    }
  };

  try {
    // Connect to your chosen server
    await client.connectToRemoteServer(
      weatherServerConfig.url,
      weatherServerConfig.auth
    );

    // Start interactive session
    await client.startChat();

  } catch (error) {
    console.error('Failed to run client:', error);
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(console.error);
}

export default RemoteMCPClient;
