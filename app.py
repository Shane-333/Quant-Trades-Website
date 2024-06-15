from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import openai
import uvicorn
from typing import List

# Initialize FastAPI app
app = FastAPI()

# Set up CORS middleware for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Function to load OpenAI API key from a file
def load_api_key(filepath):
    try:
        with open(filepath, 'r') as file:
            api_key = file.read().strip()
            return api_key
    except Exception as e:
        logger.error(f"Failed to load OpenAI API key from file: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load OpenAI API key")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load OpenAI API key from file
openai_api_key_file = "C:\\Users\\shane\\OneDrive\\Documents\\OPENAI_API_KEY.txt"
openai_api_key = load_api_key(openai_api_key_file)

if openai_api_key:
    openai.api_key = openai_api_key
else:
    logger.error("OpenAI API key not found.")
    raise HTTPException(status_code=500, detail="OpenAI API key not found.")

# Model for chat message
class ChatMessage(BaseModel):
    message: str

class SymbolsUpdate(BaseModel):
    symbols: List[str]

@app.post("/chat")
async def chat(message: ChatMessage):
    if not openai.api_key:
        logger.error("OpenAI API key not found.")
        raise HTTPException(status_code=500, detail="OpenAI API key not found.")

    try:
        response = openai.chat.completions.create(model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a financial advisor."},
            {"role": "user", "content": message.message}
        ])
        chatbot_response = response.choices[0].message.content.strip()
        return {"message": chatbot_response}
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

# Dictionary to hold the subprocess.Popen objects for each bot
processes = {}

@app.post("/start_lumibot_trend")
async def start_lumibot_trend():
    """Start the Lumibot Trend bot."""
    try:
        if 'lumibot_trend' not in processes or processes['lumibot_trend'].poll() is not None:
            processes['lumibot_trend'] = subprocess.Popen(['python', 'lumibot_trend.py'])
            logger.info("Lumibot Trend bot started.")
            return {"message": "Lumibot Trend bot started"}
        return {"message": "Lumibot Trend bot is already running"}
    except Exception as e:
        logger.error(f"Failed to start Lumibot Trend bot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start Lumibot Trend bot: {str(e)}")

@app.post("/stop_lumibot_trend")
async def stop_lumibot_trend():
    """Stop the Lumibot Trend bot."""
    try:
        if 'lumibot_trend' in processes and processes['lumibot_trend'].poll() is None:
            processes['lumibot_trend'].terminate()
            processes['lumibot_trend'].wait()  # Ensure the process has terminated
            logger.info("Lumibot Trend bot stopped.")
            return {"message": "Lumibot Trend bot stopped"}
        return {"message": "Lumibot Trend bot is not running"}
    except Exception as e:
        logger.error(f"Failed to stop Lumibot Trend bot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop Lumibot Trend bot: {str(e)}")

@app.post("/update_symbols")
async def update_symbols(symbols_update: SymbolsUpdate):
    """Update symbols for the bot."""
    try:
        symbols = symbols_update.symbols
        # Here you can add the logic to update the symbols for the bot
        # For example, save the symbols to a file or a database
        logger.info(f"Symbols updated to: {symbols}")
        return {"message": "Symbols updated"}
    except Exception as e:
        logger.error(f"Failed to update symbols: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update symbols: {str(e)}")

@app.get("/logs")
async def get_logs():
    try:
        with open('trading_bot.log', 'r') as file:
            logs = file.read()
        return JSONResponse(content={"logs": logs})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

