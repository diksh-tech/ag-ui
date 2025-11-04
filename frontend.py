import { useState, useRef, useEffect } from 'react';
import '../Chat.css';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = { role: 'user', content: input, id: Date.now() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setCurrentStreamingMessage('');

    try {
      const response = await fetch('http://localhost:8001/agent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          thread_id: 'default',
          run_id: `run-${Date.now()}`,
          messages: [...messages, userMessage].map(msg => ({
            id: msg.id.toString(),
            role: msg.role,
            content: msg.content
          })),
          tools: []
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';
      let messageId = null;
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6));
              
              if (eventData.type === 'TEXT_MESSAGE_START') {
                messageId = eventData.message_id || eventData.messageId;
              } else if (eventData.type === 'TEXT_MESSAGE_CONTENT') {
                assistantMessage += eventData.delta;
                setCurrentStreamingMessage(assistantMessage);
              } else if (eventData.type === 'TEXT_MESSAGE_CHUNK') {
                assistantMessage += eventData.delta;
                setCurrentStreamingMessage(assistantMessage);
              } else if (eventData.type === 'TEXT_MESSAGE_END') {
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: assistantMessage,
                  id: messageId || Date.now()
                }]);
                setCurrentStreamingMessage('');
              } else if (eventData.type === 'RUN_ERROR') {
                console.error('Run error:', eventData.message);
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: `Error: ${eventData.message}`,
                  id: Date.now()
                }]);
              }
            } catch (e) {
              console.error('Parse error:', e, 'Line:', line);
            }
          }
        }
      }
    } catch (error) {
      console.error('Request failed:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        id: Date.now()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-container">
      <div className="sidebar">
        <div className="logo-container">
          <img 
            src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/IndiGo_Airlines_logo.svg/2560px-IndiGo_Airlines_logo.svg.png" 
            alt="IndiGo Airlines" 
            className="airline-logo"
          />
          <h2>FlightOps Assistant</h2>
        </div>
        <div className="sidebar-info">
          <p>Welcome to IndiGo FlightOps!</p>
          <p>Ask me about:</p>
          <ul>
            <li>Flight status</li>
            <li>Delay information</li>
            <li>Equipment details</li>
            <li>Fuel summaries</li>
            <li>Passenger info</li>
            <li>Crew details</li>
          </ul>
        </div>
      </div>

      <div className="chat-main">
        <div className="messages-container">
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-content">
                {msg.content}
              </div>
            </div>
          ))}
          
          {currentStreamingMessage && (
            <div className="message assistant streaming">
              <div className="message-content">
                {currentStreamingMessage}
                <span className="cursor">▊</span>
              </div>
            </div>
          )}
          
          {isLoading && !currentStreamingMessage && (
            <div className="message assistant">
              <div className="message-content typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about flights... (e.g., 'delay info for 6E 215 on 2024-11-04')"
            disabled={isLoading}
            rows="1"
          />
          <button onClick={sendMessage} disabled={isLoading || !input.trim()}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chat;
                      ############################################
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.chat-container {
  display: flex;
  height: 100vh;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: #f5f5f5;
}

.sidebar {
  width: 280px;
  background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
  color: white;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 10px rgba(0,0,0,0.1);
}

.logo-container {
  text-align: center;
  margin-bottom: 2rem;
}

.airline-logo {
  width: 180px;
  height: auto;
  background: white;
  padding: 1rem;
  border-radius: 12px;
  margin-bottom: 1rem;
}

.sidebar h2 {
  font-size: 1.3rem;
  font-weight: 600;
}

.sidebar-info {
  margin-top: 2rem;
}

.sidebar-info p {
  margin-bottom: 1rem;
  line-height: 1.6;
}

.sidebar-info ul {
  list-style: none;
  padding-left: 0;
}

.sidebar-info li {
  padding: 0.5rem 0;
  padding-left: 1.5rem;
  position: relative;
}

.sidebar-info li:before {
  content: "✈";
  position: absolute;
  left: 0;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message {
  display: flex;
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-content {
  max-width: 70%;
  padding: 1rem 1.5rem;
  border-radius: 18px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.message.user .message-content {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: #f1f5f9;
  color: #1e293b;
  border-bottom-left-radius: 4px;
}

.message.streaming .cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.typing {
  display: flex;
  gap: 4px;
  padding: 1rem 1.5rem !important;
}

.typing span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
  animation: typing 1.4s infinite;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-10px); }
}

.input-container {
  padding: 1.5rem 2rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 1rem;
  background: white;
}

.input-container textarea {
  flex: 1;
  padding: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  font-size: 1rem;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  max-height: 120px;
}

.input-container textarea:focus {
  border-color: #3b82f6;
}

.input-container button {
  padding: 1rem 1.5rem;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-container button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.input-container button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.messages-container::-webkit-scrollbar {
  width: 8px;
}

.messages-container::-webkit-scrollbar-track {
  background: #f1f5f9;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
############################################################
import Chat from './components/Chat';

function App() {
  return <Chat />;
}

export default App;
############################################################
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
#########################################################
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#root {
  height: 100vh;
  overflow: hidden;
}
#####################################
{
  "name": "flightops-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext js,jsx --report-unused-disable-directives --max-warnings 0"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "eslint": "^8.57.0",
    "eslint-plugin-react": "^7.34.2",
    "eslint-plugin-react-hooks": "^4.6.2",
    "eslint-plugin-react-refresh": "^0.4.7",
    "vite": "^5.3.1"
  }
}
#############################################################
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/agent': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      }
    }
  }
})
