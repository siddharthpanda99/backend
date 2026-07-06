import os
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import base64
import logging

try:
    from azure.ai.voicelive.aio import connect
    from azure.identity.aio import DefaultAzureCredential
except ImportError:
    connect = None

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/stream")
async def voicelive_websocket_stream(websocket: WebSocket):
    await websocket.accept()

    if not connect:
        await websocket.send_text(json.dumps({"type": "error", "message": "azure-ai-voicelive package not installed"}))
        await websocket.close()
        return

    endpoint = os.environ.get("AZURE_COGNITIVE_SERVICES_ENDPOINT")
    
    if not endpoint:
        # Fallback to dummy or mock for dev if needed, or error
        endpoint = "https://eastus.api.cognitive.microsoft.com"

    try:
        async with connect(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
            model="gpt-4o-realtime-preview",
            credential_scopes=["https://cognitiveservices.azure.com/.default"]
        ) as conn:
            
            # Initial Session config
            await conn.session.update(session={
                "instructions": "You are a helpful voice assistant.",
                "modalities": ["text", "audio"],
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            })

            # Task to read from client and forward to Azure
            async def read_from_client():
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            break
                        
                        # We expect JSON control messages or binary audio
                        if message.get("bytes") is not None:
                            # Forward raw audio bytes as base64 to Azure
                            b64_audio = base64.b64encode(message["bytes"]).decode()
                            await conn.input_audio_buffer.append(audio=b64_audio)
                        elif message.get("text") is not None:
                            try:
                                data = json.loads(message["text"])
                                if data.get("action") == "commit":
                                    await conn.input_audio_buffer.commit()
                                    await conn.response.create()
                                elif data.get("action") == "cancel":
                                    await conn.response.cancel()
                                    await conn.output_audio_buffer.clear()
                            except Exception as e:
                                logger.error(f"Error parsing client JSON: {e}")
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.error(f"Client read error: {e}")

            # Task to read from Azure and forward to client
            async def read_from_azure():
                try:
                    async for event in conn:
                        if event.type == "response.audio.delta":
                            # Send binary audio back to client
                            audio_bytes = base64.b64decode(event.delta)
                            await websocket.send_bytes(audio_bytes)
                        elif event.type == "response.audio_transcript.delta":
                            await websocket.send_text(json.dumps({
                                "type": "transcript_delta",
                                "delta": event.delta
                            }))
                        elif event.type == "conversation.item.input_audio_transcription.completed":
                            await websocket.send_text(json.dumps({
                                "type": "user_transcript",
                                "transcript": event.transcript
                            }))
                        elif event.type in ["response.done", "response.created", "error"]:
                            await websocket.send_text(json.dumps({
                                "type": "event",
                                "event_type": event.type,
                                "data": str(event)
                            }))
                except Exception as e:
                    logger.error(f"Azure read error: {e}")
                    try:
                        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
                    except:
                        pass

            client_task = asyncio.create_task(read_from_client())
            azure_task = asyncio.create_task(read_from_azure())

            done, pending = await asyncio.wait(
                [client_task, azure_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

    except Exception as e:
        logger.error(f"VoiceLive connection error: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
            await websocket.close()
        except:
            pass
