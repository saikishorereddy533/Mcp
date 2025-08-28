import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn } from 'child_process';
import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';

dotenv.config();

class MCPClient {
  constructor() {
    this.client = null;
    this.serverProcess = null;
    this.gemini = new GoogleGenAI({
      apiKey: process.env.GOOGLE_API_KEY
    });
  }

  /**
   * Start the MCP server process and connect to it
   */
  async startServer() {
    try {
      // Create the server process using uvx (as shown in your config)
      this.serverProcess = spawn('uvx', [
        '--from', 
        'git+https://github.com/henryhabib/mcpserverexample.git',
        'mcp-server'
      ], {
        stdio: ['pipe', 'pipe', 'pipe'] // We'll use stdin/stdout for communication
      });

      // Handle server process errors
      this.serverProcess.stderr.on('data', (data) => {
        console.error('Server stderr:', data.toString());
      });

      this.serverProcess.on('error', (error) => {
        console.error('Server process error:', error);
      });

      this.serverProcess.on('close', (code) => {
        console.log(`Server process exited with code ${code}`);
      });

      // Create stdio transport for the server process
      const transport = new StdioClientTransport({
        command: 'uvx',
        args: [
          '--from', 
          'git+https://github.com/henryhabib/mcpserverexample.git',
          'mcp-server'
        ]
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

      await this.client.connect(transport);
      console.log('✅ Connected to MCP server');

      return true;

    } catch (error) {
      console.error('❌ Failed to start server:', error.message);
      throw error;
    }
  }

  /**
   * Process query using Gemini with MCP tools
   */
  async processQuery(query) {
    if (!this.client) {
      throw new Error('Client not connected to server');
    }

    try {
      // Get available tools from the server
      const toolsResponse = await this.client.listTools();
      const availableTools = toolsResponse.tools;

      // Prepare tools for Gemini
      const geminiTools = availableTools.map(tool => ({
        name: tool.name,
        description: tool.description,
        parameters: tool.inputSchema
      }));

      // Generate response with Gemini
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

      let finalResponse = '';
      const content = response.candidates[0].content;

      for (const part of content.parts) {
        if (part.text) {
          finalResponse += part.text;
        } else if (part.functionCall) {
          // Execute tool call on the MCP server
          const toolResult = await this.client.callTool({
            name: part.functionCall.name,
            arguments: part.functionCall.args
          });

          // Get final response with tool results
          const followUpResponse = await this.gemini.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: [{
              role: 'user',
              parts: [{
                text: `Tool result: ${JSON.stringify(toolResult.content)}\nOriginal query: ${query}`
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
  async startInteractiveSession() {
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
          await this.cleanup();
          return;
        }

        try {
          const response = await this.processQuery(query);
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
   * Cleanup resources
   */
  async cleanup() {
    if (this.client) {
      await this.client.close();
    }
    if (this.serverProcess) {
      this.serverProcess.kill();
    }
    console.log('👋 Cleaned up resources');
  }
}

// Main execution
async function main() {
  const client = new MCPClient();

  try {
    // Start the server and connect
    await client.startServer();
    
    // Start interactive session
    await client.startInteractiveSession();

  } catch (error) {
    console.error('Failed to run client:', error);
    await client.cleanup();
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(console.error);
}

export default MCPClient;
