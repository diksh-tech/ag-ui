import os
import uuid
import json
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FlightOps AG-UI Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import AG-UI components
try:
    from ag_ui.core import (
        RunAgentInput,
        EventType,
        RunStartedEvent,
        RunFinishedEvent,
        RunErrorEvent,
        TextMessageStartEvent,
        TextMessageContentEvent,
        TextMessageEndEvent,
    )
    from ag_ui.encoder import EventEncoder
    AGUI_AVAILABLE = True
except ImportError:
    AGUI_AVAILABLE = False
    print("⚠️ AG-UI not installed, using fallback")

from mcp_client import FlightOpsMCPClient

class FlightOpsAgent:
    def __init__(self):
        self.mcp_client = FlightOpsMCPClient()
        self.connected = False

    async def ensure_connected(self):
        """Ensure MCP client is connected"""
        if not self.connected:
            await self.mcp_client.connect()
            self.connected = True

    async def process_query(self, user_message: str):
        """Process user query and return results"""
        await self.ensure_connected()
        return await self.mcp_client.run_query(user_message)

# Global agent instance
agent = FlightOpsAgent()

@app.post("/agent")
async def agent_endpoint(request: Request):
    """Main AG-UI agent endpoint"""
    if not AGUI_AVAILABLE:
        raise HTTPException(status_code=500, detail="AG-UI not available")

    try:
        # Parse request
        body = await request.json()
        
        # Extract user message
        messages = body.get("messages", [])
        user_message = None
        
        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        print(f"📥 Processing query: {user_message}")

        # Get accept header for encoder
        accept_header = request.headers.get("accept", "text/event-stream")
        encoder = EventEncoder(accept=accept_header)

        async def generate_events():
            """Generate AG-UI events"""
            try:
                # Emit run started
                yield encoder.encode(RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id=body.get("thread_id", "default"),
                    run_id=body.get("run_id", f"run-{uuid.uuid4().hex[:8]}")
                ))

                # Process the query
                result = await agent.process_query(user_message)
                
                # Extract response text
                if isinstance(result, dict):
                    if "summary" in result and isinstance(result["summary"], dict):
                        response_text = result["summary"].get("summary", "No summary available")
                    elif "summary" in result:
                        response_text = result["summary"]
                    elif "error" in result:
                        response_text = f"Error: {result['error']}"
                    else:
                        response_text = json.dumps(result, indent=2)
                else:
                    response_text = str(result)

                # Ensure response_text is a string
                if not isinstance(response_text, str):
                    response_text = str(response_text)

                # Emit text message start
                message_id = f"msg-{uuid.uuid4().hex[:8]}"
                yield encoder.encode(TextMessageStartEvent(
                    type=EventType.TEXT_MESSAGE_START,
                    message_id=message_id,
                    role="assistant"
                ))

                # Stream response word by word
                if response_text:
                    words = response_text.split()
                    for word in words:
                        yield encoder.encode(TextMessageContentEvent(
                            type=EventType.TEXT_MESSAGE_CONTENT,
                            message_id=message_id,
                            delta=word + " "
                        ))
                        await asyncio.sleep(0.05)  # Simulate streaming

                # Emit text message end
                yield encoder.encode(TextMessageEndEvent(
                    type=EventType.TEXT_MESSAGE_END,
                    message_id=message_id
                ))

                # Emit run finished
                yield encoder.encode(RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=body.get("thread_id", "default"),
                    run_id=body.get("run_id", f"run-{uuid.uuid4().hex[:8]}")
                ))

            except Exception as error:
                print(f"❌ Error in event generation: {error}")
                yield encoder.encode(RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message=str(error)
                ))

        return StreamingResponse(
            generate_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )

    except Exception as e:
        print(f"❌ Server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"status": "healthy", "service": "FlightOps AG-UI Server"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        await agent.ensure_connected()
        tools = await agent.mcp_client.list_tools()
        return {
            "status": "healthy",
            "mcp_connected": True,
            "tools_available": len(tools.get("tools", {})),
            "ag_ui_available": AGUI_AVAILABLE
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mcp_connected": False,
            "error": str(e),
            "ag_ui_available": AGUI_AVAILABLE
        }

@app.get("/tools")
async def list_tools():
    """List available MCP tools"""
    try:
        await agent.ensure_connected()
        return await agent.mcp_client.list_tools()
    except Exception as e:
        return {"error": str(e)}

@app.post("/query")
async def direct_query(request: Request):
    """Direct query endpoint for testing"""
    body = await request.json()
    user_query = body.get("query", "")
    
    try:
        result = await agent.process_query(user_query)
        return result
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FlightOps AG-UI Server...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
