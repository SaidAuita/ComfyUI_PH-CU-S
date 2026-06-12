import os
import json
import base64
import uuid
from pathlib import Path

import folder_paths
from aiohttp import web, WSMsgType
from server import PromptServer

PLUGIN_ROOT  = Path(os.path.dirname(os.path.abspath(__file__)))
EXCHANGE_DIR = PLUGIN_ROOT / "exchange"
EXCHANGE_DIR.mkdir(parents=True, exist_ok=True)


class BridgeServer:
    """Manages active WebSocket connections from Photoshop and the ComfyUI browser."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._ps_clients:  list[str] = []
        self._ui_clients:  list[str] = []

    def register(self, client_id: str, ws, role: str):
        self._sessions[client_id] = {"ws": ws, "role": role}
        if role == "ps":
            self._ps_clients.append(client_id)
        elif role == "cm":
            self._ui_clients.append(client_id)
        print(f"[PH-CU-S] + {role} {client_id[:8]}")

    def unregister(self, client_id: str):
        session = self._sessions.pop(client_id, None)
        if not session:
            return
        role = session["role"]
        if role == "ps" and client_id in self._ps_clients:
            self._ps_clients.remove(client_id)
            print(f"[PH-CU-S] - ps {client_id[:8]}")
        elif role == "cm" and client_id in self._ui_clients:
            self._ui_clients.remove(client_id)
            print(f"[PH-CU-S] - cm {client_id[:8]}")

    async def broadcast(self, targets: list[str], key: str, payload=True):
        if not targets:
            return
        data = json.dumps({key: payload}) if key else payload
        for cid in list(targets):
            session = self._sessions.get(cid)
            if session:
                try:
                    await session["ws"].send_str(data)
                except Exception as exc:
                    print(f"[PH-CU-S] Send error {cid[:8]}: {exc}")

    @staticmethod
    def _write_binary(filename: str, data_b64: str, client_id: str = ""):
        suffix = f"_{client_id}" if client_id else ""
        dot = filename.rfind(".")
        if dot != -1:
            actual_name = filename[:dot] + suffix + filename[dot:]
        else:
            actual_name = filename + suffix
        (EXCHANGE_DIR / actual_name).write_bytes(base64.b64decode(data_b64))

    @staticmethod
    def _write_text(filename: str, text: str, client_id: str = ""):
        suffix = f"_{client_id}" if client_id else ""
        dot = filename.rfind(".")
        if dot != -1:
            actual_name = filename[:dot] + suffix + filename[dot:]
        else:
            actual_name = filename + suffix
        (EXCHANGE_DIR / actual_name).write_text(text, encoding="utf-8")

    async def handle_ps_message(self, payload: dict, client_id: str = ""):
        if "canvasBase64" in payload:
            self._write_binary("canvas.png", payload["canvasBase64"], client_id)
        if "maskBase64" in payload:
            self._write_binary("mask.png", payload["maskBase64"], client_id)
        if "prompt" in payload:
            self._write_text("prompt.txt", payload["prompt"], client_id)
            print(f"[PH-CU-S] prompt{f'_{client_id}' if client_id else ''} ← {payload['prompt'][:60]!r}")
        if "negative_prompt" in payload:
            self._write_text("negative.txt", payload["negative_prompt"], client_id)

        workflow_path = payload.get("workflowPath")
        if workflow_path:
            try:
                workflow_json = json.loads(Path(workflow_path).read_text(encoding="utf-8"))
                print(f"[PH-CU-S] workflow ← {workflow_path}")
                if payload.get("queue"):
                    print("[PH-CU-S] Queue trigger (with workflow load) →")
                    await self.broadcast(self._ui_clients, "loadAndQueue", workflow_json)
                else:
                    await self.broadcast(self._ui_clients, "loadWorkflow", workflow_json)
                return
            except Exception as exc:
                print(f"[PH-CU-S] Cannot load workflow '{workflow_path}': {exc}")

        if payload.get("queue"):
            print("[PH-CU-S] Queue trigger →")
            await self.broadcast(self._ui_clients, "queue", True)

    async def handle_cm_message(self, payload: dict):
        await self.broadcast(self._ps_clients, "", json.dumps(payload))


_bridge = BridgeServer()


@PromptServer.instance.routes.get("/phcus/ws")
async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    client_id = request.query.get("clientId") or str(uuid.uuid4())
    role       = request.query.get("platform", "unknown")

    _bridge.register(client_id, ws, role)

    if role == "ps" and _bridge._ui_clients:
        await _bridge.broadcast(_bridge._ui_clients, "photoshopConnected", True)
    elif role == "cm" and _bridge._ps_clients:
        await _bridge.broadcast(_bridge._ui_clients, "photoshopConnected", True)

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    print(f"[PH-CU-S] Bad JSON from {client_id[:8]}")
                    continue
                if role == "ps":
                    await _bridge.handle_ps_message(data, client_id)
                elif role == "cm":
                    await _bridge.handle_cm_message(data)
            elif msg.type == WSMsgType.ERROR:
                print(f"[PH-CU-S] WS error: {ws.exception()}")
    finally:
        _bridge.unregister(client_id)

    return ws


@PromptServer.instance.routes.get("/phcus/renderdone")
async def renderdone_handler(request):
    filename = request.rel_url.query.get("filename")
    client_id = request.rel_url.query.get("client_id")
    if not filename:
        return web.Response(status=400, text="filename required")
    try:
        img_path = Path(folder_paths.get_temp_directory()) / filename
        encoded  = base64.b64encode(img_path.read_bytes()).decode()
        print(f"[PH-CU-S] Delivering result ({len(encoded)} bytes) to client_id={client_id}")
        if client_id:
            await _bridge.broadcast([client_id], "render", encoded)
        else:
            await _bridge.broadcast(_bridge._ps_clients, "render", encoded)
        return web.Response(text="ok")
    except Exception as exc:
        print(f"[PH-CU-S] renderdone error: {exc}")
        return web.Response(status=500, text=str(exc))
