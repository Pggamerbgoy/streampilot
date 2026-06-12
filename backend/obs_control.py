import asyncio
import base64
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import websockets


OBS_EVENT_SUBSCRIPTIONS = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6) | (1 << 16)

SAFE_ACTIONS = {
    "create_scene",
    "switch_scene",
    "set_preview_scene",
    "trigger_transition",
    "set_source_enabled",
    "set_source_transform",
    "set_scene_item_index",
    "create_input",
    "set_input_settings",
    "set_input_mute",
    "set_input_volume",
    "set_input_monitor_type",
    "start_record",
    "pause_record",
    "resume_record",
    "start_replay_buffer",
    "save_replay_buffer",
}

DANGEROUS_ACTIONS = {
    "start_stream",
    "stop_stream",
    "stop_record",
    "stop_replay_buffer",
    "start_virtual_cam",
    "stop_virtual_cam",
    "set_stream_service_settings",
    "set_output_settings",
    "remove_input",
    "remove_scene",
    "set_current_profile",
    "set_current_scene_collection",
}


@dataclass
class ObsConfig:
    host: str = "127.0.0.1"
    port: int = 4455
    password: str = ""

    @classmethod
    def from_payload(cls, payload: Optional[Dict[str, Any]] = None) -> "ObsConfig":
        payload = payload or {}
        host = str(payload.get("host") or os.getenv("OBS_WS_HOST") or "127.0.0.1").strip() or "127.0.0.1"
        try:
            port = int(payload.get("port") or os.getenv("OBS_WS_PORT") or 4455)
        except Exception:
            port = 4455
        password = str(payload.get("password") if payload.get("password") is not None else os.getenv("OBS_WS_PASSWORD") or "")
        return cls(host=host, port=port, password=password)

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    def public(self) -> Dict[str, Any]:
        return {"host": self.host, "port": self.port, "password_configured": bool(self.password)}


class ObsControlError(RuntimeError):
    def __init__(self, message: str, category: str = "obs_error"):
        super().__init__(message)
        self.category = category


class ObsWebSocketClient:
    def __init__(self, config: ObsConfig):
        self.config = config
        self.websocket = None
        self.connected = False
        self.version: Dict[str, Any] = {}
        self.available_requests = set()
        self._pending: Dict[str, asyncio.Future] = {}
        self._events: List[Dict[str, Any]] = []
        self._event_queues: List[asyncio.Queue] = []
        self._receiver_task: Optional[asyncio.Task] = None
        self._last_meter_event = 0.0

    async def connect(self) -> Dict[str, Any]:
        self.websocket = await websockets.connect(self.config.url)
        hello = await self._recv_json()
        if hello.get("op") != 0:
            raise ObsControlError("OBS did not send a valid hello message.", "protocol_error")
        hello_data = hello.get("d", {})
        identify_data = {"rpcVersion": min(int(hello_data.get("rpcVersion") or 1), 1), "eventSubscriptions": OBS_EVENT_SUBSCRIPTIONS}
        authentication = hello_data.get("authentication")
        if authentication:
            if not self.config.password:
                raise ObsControlError("OBS requires a WebSocket password.", "auth_required")
            identify_data["authentication"] = _obs_auth_response(
                self.config.password,
                authentication.get("salt", ""),
                authentication.get("challenge", ""),
            )
        await self._send_json({"op": 1, "d": identify_data})
        identified = await self._recv_json()
        if identified.get("op") != 2:
            raise ObsControlError("OBS authentication failed.", "auth_error")
        self.connected = True
        self._receiver_task = asyncio.create_task(self._receiver())
        self.version = await self.request("GetVersion")
        self.available_requests = set(self.version.get("availableRequests") or [])
        return self.version

    async def disconnect(self) -> Dict[str, Any]:
        self.connected = False
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except BaseException:
                pass
        if self.websocket:
            await self.websocket.close()
        self.websocket = None
        for future in list(self._pending.values()):
            if not future.done():
                future.cancel()
        self._pending.clear()
        return {"ok": True, "connected": False}

    async def request(self, request_type: str, request_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.connected or not self.websocket:
            raise ObsControlError("OBS is not connected.", "not_connected")
        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = future
        await self._send_json({"op": 6, "d": {"requestType": request_type, "requestId": request_id, "requestData": request_data or {}}})
        try:
            return await asyncio.wait_for(future, timeout=12)
        finally:
            self._pending.pop(request_id, None)

    async def event_stream(self) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._event_queues.append(queue)
        for event in self._events[-10:]:
            await queue.put(event)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._event_queues:
                self._event_queues.remove(queue)

    async def _receiver(self) -> None:
        while self.connected and self.websocket:
            message = await self._recv_json()
            op_code = message.get("op")
            data = message.get("d", {})
            if op_code == 7:
                request_id = data.get("requestId")
                future = self._pending.get(request_id)
                if future and not future.done():
                    status = data.get("requestStatus") or {}
                    if not status.get("result", False):
                        future.set_exception(
                            ObsControlError(status.get("comment") or "OBS request failed.", f"obs_status_{status.get('code', 'error')}")
                        )
                    else:
                        future.set_result(data.get("responseData") or {})
            elif op_code == 5:
                await self._publish_event(_normalize_obs_event(data))

    async def _publish_event(self, event: Dict[str, Any]) -> None:
        if event.get("eventType") == "InputVolumeMeters":
            now = time.monotonic()
            if now - self._last_meter_event < 0.25:
                return
            self._last_meter_event = now
        self._events.append(event)
        self._events = self._events[-50:]
        for queue in list(self._event_queues):
            if queue.full():
                try:
                    queue.get_nowait()
                except Exception:
                    pass
            await queue.put(event)

    async def _recv_json(self) -> Dict[str, Any]:
        raw = await self.websocket.recv()
        return json.loads(raw)

    async def _send_json(self, payload: Dict[str, Any]) -> None:
        await self.websocket.send(json.dumps(payload))


class ObsManager:
    def __init__(self, client_factory: Optional[Callable[[ObsConfig], Any]] = None):
        self.client_factory = client_factory or ObsWebSocketClient
        self.client: Optional[Any] = None
        self.config: Optional[ObsConfig] = None

    async def connect(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.client:
            await self.disconnect()
        self.config = ObsConfig.from_payload(payload)
        self.client = self.client_factory(self.config)
        try:
            version = await self.client.connect()
            return {
                "ok": True,
                "connected": True,
                "config": self.config.public(),
                "version": _version_summary(version),
                "available_requests_count": len(version.get("availableRequests") or []),
            }
        except Exception as exc:
            self.client = None
            return _obs_error("connect", exc, config=self.config.public())

    async def disconnect(self) -> Dict[str, Any]:
        if not self.client:
            return {"ok": True, "connected": False, "message": "OBS was not connected."}
        try:
            result = await self.client.disconnect()
            return {"ok": True, **result}
        finally:
            self.client = None

    async def status(self) -> Dict[str, Any]:
        if not self._connected():
            return {"ok": True, "connected": False, "message": "OBS is not connected.", "status": {}}
        try:
            responses = await _request_many(
                self.client,
                [
                    ("GetVersion", {}),
                    ("GetStreamStatus", {}),
                    ("GetRecordStatus", {}),
                    ("GetReplayBufferStatus", {}),
                    ("GetVirtualCamStatus", {}),
                    ("GetCurrentProgramScene", {}),
                    ("GetStudioModeEnabled", {}),
                ],
            )
            return {
                "ok": True,
                "connected": True,
                "version": _version_summary(responses.get("GetVersion", {})),
                "stream": responses.get("GetStreamStatus", {}),
                "record": responses.get("GetRecordStatus", {}),
                "replay_buffer": responses.get("GetReplayBufferStatus", {}),
                "virtual_cam": responses.get("GetVirtualCamStatus", {}),
                "current_scene": responses.get("GetCurrentProgramScene", {}),
                "studio_mode": responses.get("GetStudioModeEnabled", {}),
                "audio_meters": "event_stream_only",
            }
        except Exception as exc:
            return _obs_error("status", exc)

    async def scenes(self) -> Dict[str, Any]:
        if not self._connected():
            return {"ok": False, "connected": False, "scenes": [], "message": "Connect OBS first."}
        try:
            scene_list = await self.client.request("GetSceneList")
            scenes = scene_list.get("scenes") or []
            scene_details = []
            for scene in scenes:
                scene_name = scene.get("sceneName")
                if not scene_name:
                    continue
                try:
                    items = await self.client.request("GetSceneItemList", {"sceneName": scene_name})
                    scene_details.append({**scene, "items": items.get("sceneItems") or []})
                except Exception as exc:
                    scene_details.append({**scene, "items": [], "error": str(exc)})
            preview = {}
            try:
                preview = await self.client.request("GetCurrentPreviewScene")
            except Exception:
                preview = {}
            return {
                "ok": True,
                "connected": True,
                "current_program_scene": scene_list.get("currentProgramSceneName"),
                "current_preview_scene": preview.get("currentPreviewSceneName"),
                "scenes": scene_details,
            }
        except Exception as exc:
            return _obs_error("scenes", exc, scenes=[])

    async def action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action") or "").strip()
        confirm = bool(payload.get("confirm"))
        params = payload.get("params") or {}
        if action in DANGEROUS_ACTIONS and not confirm:
            return {
                "ok": False,
                "action": action,
                "requires_confirmation": True,
                "message": f"{action} needs explicit confirmation.",
                "next_actions": ["Review the OBS state, then retry with confirm=true."],
            }
        if not self._connected():
            return {"ok": False, "connected": False, "action": action, "message": "Connect OBS first."}
        try:
            request_type, request_data = await self._map_action(action, params)
            self._ensure_request_supported(request_type)
            response = await self.client.request(request_type, request_data)
            return {
                "ok": True,
                "connected": True,
                "action": action,
                "request_type": request_type,
                "request_data": request_data,
                "requires_confirmation": False,
                "obs_response": response,
                "message": f"{action} applied.",
                "next_actions": [],
            }
        except Exception as exc:
            return _obs_error("action", exc, action=action)

    async def autopilot_setup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._connected():
            return {"ok": False, "connected": False, "message": "Connect OBS first.", "planned_actions": []}
        topic = str(payload.get("topic") or payload.get("game") or "Live Stream").strip() or "Live Stream"
        try:
            input_kinds = await self.client.request("GetInputKindList")
            version = await self.client.request("GetVersion")
            scene_list = await self.client.request("GetSceneList")
        except Exception as exc:
            return _obs_error("autopilot_preflight", exc, planned_actions=[])

        kinds = input_kinds.get("inputKinds") or input_kinds.get("inputKindList") or []
        text_kind = _select_text_input_kind(version, kinds)
        browser_kind = "browser_source" if "browser_source" in kinds else None
        existing_scenes = {scene.get("sceneName") for scene in scene_list.get("scenes") or []}
        scene_name = _safe_obs_name(f"StreamPilot - {topic}", 48)
        planned = _autopilot_actions(scene_name, topic, text_kind=text_kind, browser_kind=browser_kind, scene_exists=scene_name in existing_scenes)
        applied: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for item in planned:
            action = item.get("action")
            if item.get("skip_reason"):
                skipped.append(item)
                continue
            result = await self.action({"action": action, "params": item.get("params") or {}, "confirm": False})
            record = {**item, "result": result}
            if result.get("ok"):
                applied.append(record)
            else:
                failed.append(record)

        return {
            "ok": not failed,
            "connected": True,
            "topic": topic,
            "scene_name": scene_name,
            "requires_confirmation": False,
            "partial_success": bool(applied and failed),
            "planned_actions": planned,
            "applied_actions": applied,
            "skipped_actions": skipped,
            "failed_actions": failed,
            "manual_cleanup_notes": _cleanup_notes(failed, applied),
            "message": "OBS studio setup completed." if not failed else "OBS studio setup partially completed.",
        }

    async def event_stream(self) -> AsyncIterator[Dict[str, Any]]:
        if not self._connected():
            yield {"eventType": "Disconnected", "eventData": {"message": "OBS is not connected."}}
            return
        async for event in self.client.event_stream():
            yield event

    def _connected(self) -> bool:
        return bool(self.client and getattr(self.client, "connected", False))

    def _ensure_request_supported(self, request_type: str) -> None:
        available = set(getattr(self.client, "available_requests", set()) or [])
        version = getattr(self.client, "version", {}) or {}
        available.update(version.get("availableRequests") or [])
        if available and request_type not in available:
            raise ObsControlError(f"OBS does not support {request_type}.", "unsupported_request")

    async def _map_action(self, action: str, params: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        mappings = {
            "create_scene": ("CreateScene", {"sceneName": params.get("sceneName")}),
            "switch_scene": ("SetCurrentProgramScene", {"sceneName": params.get("sceneName")}),
            "set_preview_scene": ("SetCurrentPreviewScene", {"sceneName": params.get("sceneName")}),
            "trigger_transition": ("TriggerStudioModeTransition", {}),
            "set_source_enabled": (
                "SetSceneItemEnabled",
                {
                    "sceneName": params.get("sceneName"),
                    "sceneItemId": params.get("sceneItemId"),
                    "sceneItemEnabled": bool(params.get("enabled")),
                },
            ),
            "set_source_transform": (
                "SetSceneItemTransform",
                {"sceneName": params.get("sceneName"), "sceneItemId": params.get("sceneItemId"), "sceneItemTransform": params.get("transform") or {}},
            ),
            "set_scene_item_index": (
                "SetSceneItemIndex",
                {"sceneName": params.get("sceneName"), "sceneItemId": params.get("sceneItemId"), "sceneItemIndex": params.get("sceneItemIndex")},
            ),
            "create_input": (
                "CreateInput",
                {
                    "sceneName": params.get("sceneName"),
                    "inputName": params.get("inputName"),
                    "inputKind": params.get("inputKind"),
                    "inputSettings": params.get("inputSettings") or {},
                    "sceneItemEnabled": params.get("sceneItemEnabled", True),
                },
            ),
            "set_input_settings": (
                "SetInputSettings",
                {"inputName": params.get("inputName"), "inputSettings": params.get("inputSettings") or {}, "overlay": bool(params.get("overlay", True))},
            ),
            "set_input_mute": ("SetInputMute", {"inputName": params.get("inputName"), "inputMuted": bool(params.get("muted"))}),
            "set_input_volume": ("SetInputVolume", {"inputName": params.get("inputName"), "inputVolumeMul": float(params.get("volumeMul", 1.0))}),
            "set_input_monitor_type": ("SetInputAudioMonitorType", {"inputName": params.get("inputName"), "monitorType": params.get("monitorType")}),
            "start_record": ("StartRecord", {}),
            "stop_record": ("StopRecord", {}),
            "pause_record": ("PauseRecord", {}),
            "resume_record": ("ResumeRecord", {}),
            "start_stream": ("StartStream", {}),
            "stop_stream": ("StopStream", {}),
            "start_virtual_cam": ("StartVirtualCam", {}),
            "stop_virtual_cam": ("StopVirtualCam", {}),
            "start_replay_buffer": ("StartReplayBuffer", {}),
            "stop_replay_buffer": ("StopReplayBuffer", {}),
            "save_replay_buffer": ("SaveReplayBuffer", {}),
            "set_stream_service_settings": (
                "SetStreamServiceSettings",
                {"streamServiceType": params.get("streamServiceType") or "rtmp_common", "streamServiceSettings": params.get("streamServiceSettings") or {}},
            ),
            "set_output_settings": ("SetOutputSettings", {"outputName": params.get("outputName"), "outputSettings": params.get("outputSettings") or {}}),
            "remove_input": ("RemoveInput", {"inputName": params.get("inputName")}),
            "remove_scene": ("RemoveScene", {"sceneName": params.get("sceneName")}),
            "set_current_profile": ("SetCurrentProfile", {"profileName": params.get("profileName")}),
            "set_current_scene_collection": ("SetCurrentSceneCollection", {"sceneCollectionName": params.get("sceneCollectionName")}),
        }
        if action not in mappings:
            raise ObsControlError(f"Unsupported OBS action: {action}", "unsupported_action")
        request_type, request_data = mappings[action]
        return request_type, _drop_none(request_data)


async def _request_many(client: Any, requests: List[tuple[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    responses: Dict[str, Dict[str, Any]] = {}
    for request_type, request_data in requests:
        try:
            responses[request_type] = await client.request(request_type, request_data)
        except Exception as exc:
            responses[request_type] = {"error": str(exc)}
    return responses


def _obs_auth_response(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode("utf-8")).digest()).decode("utf-8")
    return base64.b64encode(hashlib.sha256((secret + challenge).encode("utf-8")).digest()).decode("utf-8")


def _version_summary(version: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "obs_version": version.get("obsVersion"),
        "obs_websocket_version": version.get("obsWebSocketVersion"),
        "rpc_version": version.get("rpcVersion"),
        "platform": version.get("platform"),
        "platform_description": version.get("platformDescription"),
    }


def _obs_error(context: str, exc: Exception, **extra: Any) -> Dict[str, Any]:
    return {
        "ok": False,
        "connected": False,
        "context": context,
        "error_category": getattr(exc, "category", "obs_error"),
        "error": str(exc),
        **extra,
    }


def _normalize_obs_event(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eventType": data.get("eventType"),
        "eventIntent": data.get("eventIntent"),
        "eventData": data.get("eventData") or {},
        "received_at": time.time(),
    }


def _select_text_input_kind(version: Dict[str, Any], input_kinds: List[str]) -> Optional[str]:
    platform = str(version.get("platform") or "").lower()
    if "windows" in platform or platform == "win32":
        for kind in ("text_gdiplus_v3", "text_gdiplus", "text_ft2_source"):
            if kind in input_kinds:
                return kind
    for kind in ("text_ft2_source", "text_gdiplus_v3", "text_gdiplus"):
        if kind in input_kinds:
            return kind
    return None


def _autopilot_actions(
    scene_name: str,
    topic: str,
    text_kind: Optional[str],
    browser_kind: Optional[str],
    scene_exists: bool,
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    if not scene_exists:
        actions.append({"action": "create_scene", "request_type": "CreateScene", "params": {"sceneName": scene_name}})
    actions.append({"action": "switch_scene", "params": {"sceneName": scene_name}})
    if text_kind:
        actions.append(
            {
                "action": "create_input",
                "params": {
                    "sceneName": scene_name,
                    "inputName": _safe_obs_name(f"{topic} Title", 64),
                    "inputKind": text_kind,
                    "inputSettings": {"text": f"{topic} - LIVE", "font": {"face": "Arial", "size": 42}},
                },
            }
        )
    else:
        actions.append({"action": "create_input", "params": {}, "skip_reason": "No compatible text source kind found."})
    if browser_kind:
        actions.append(
            {
                "action": "create_input",
                "params": {
                    "sceneName": scene_name,
                    "inputName": "StreamPilot Chat Overlay",
                    "inputKind": browser_kind,
                    "inputSettings": {"url": "about:blank", "width": 420, "height": 720},
                },
            }
        )
    else:
        actions.append({"action": "create_input", "params": {}, "skip_reason": "Browser source is not available in this OBS install."})
    return actions


def _cleanup_notes(failed: List[Dict[str, Any]], applied: List[Dict[str, Any]]) -> List[str]:
    notes = []
    if failed and applied:
        notes.append("OBS was changed before one or more setup actions failed; review applied actions before going live.")
    for item in failed:
        notes.append(f"Failed action: {item.get('action')}")
    return notes


def _safe_obs_name(value: str, limit: int) -> str:
    cleaned = " ".join(str(value or "").split())
    return cleaned[:limit] or "StreamPilot"


def _drop_none(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}
