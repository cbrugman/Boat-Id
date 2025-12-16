import asyncio
import json
import websockets
import ssl
import os

# Configuration
AIS_STREAM_URL = "wss://stream.aisstream.io/v0/stream"
LOCAL_PORT = int(os.environ.get("PORT", 8765))
API_KEY = "a05f104a2962bf16a0552a5145bce80efb3766f0" # Moved from HTML

print(f"--- Boat Tracker Proxy Server ---")
print(f"Listening on ws://localhost:{LOCAL_PORT}")
print(f"Please open boat_tracker.html in your browser.")

async def proxy_handler(client_ws):
    print(f"[Client] Connected")
    
    try:
        # 1. Connect to upstream AIS Stream
        async with websockets.connect(AIS_STREAM_URL) as ais_ws:
            print(f"[Upstream] Connected to AISStream.io")
            
            # 2. Wait for subscription message from Client (Browser)
            # The browser sends the JSON config (Bounding Boxes)
            msg_str = await client_ws.recv()
            print(f"[Client] Sent config: {msg_str[:50]}...")
            
            # 3. Inject API Key
            try:
                subscription = json.loads(msg_str)
                subscription["APIKey"] = API_KEY # Inject Secret Key here
                final_msg = json.dumps(subscription)
            except Exception as e:
                print(f"[Error] Failed to parse/inject config: {e}")
                return

            # 4. Forward subscription to AIS Stream
            await ais_ws.send(final_msg)
            print(f"[Upstream] Forwarded subscription (with API Key injected)")

            # 4. Create tasks to pipe data in both directions
            
            # Task A: Read from AIS, Send to Client
            async def upstream_to_client():
                msg_count = 0
                async for message in ais_ws:
                    if isinstance(message, bytes):
                        message = message.decode('utf-8')
                        
                    msg_count += 1
                    # print(f"[Upstream] Received msg {msg_count}: {message[:100]}...") # Verbose
                    if msg_count <= 3:
                        print(f"[DEBUG] Msg #{msg_count}: {message}")
                    elif msg_count % 10 == 1:
                        print(f"[Upstream] Receiving data... (msg #{msg_count})")
                    await client_ws.send(message)
            
            # Task B: Read from Client, Send to AIS (usually just keepalive or close)
            async def client_to_upstream():
                async for message in client_ws:
                    await ais_ws.send(message)

            # Run until one dumps
            task_a = asyncio.create_task(upstream_to_client())
            task_b = asyncio.create_task(client_to_upstream())
            
            done, pending = await asyncio.wait(
                [task_a, task_b],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                
    except websockets.exceptions.ConnectionClosed:
        print(f"[Client] Disconnected")
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        print(f"[Session] Ended")

async def main():
    async with websockets.serve(proxy_handler, "0.0.0.0", LOCAL_PORT):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping server...")
