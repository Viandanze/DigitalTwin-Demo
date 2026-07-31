"""
device_api.py
Device CRUD REST API — FastAPI Router
Week19 Day4 核心代码框架

功能:
- Device list / detail / create / update / delete
- Device status query (online / offline / warning / error)
- Batch operations (bulk create / update / delete)
- Device type and location filtering with pagination
- Designed to be imported as a FastAPI APIRouter

Usage:
    from device_api import router as device_router
    app.include_router(device_router, prefix="/api/v2", tags=["devices"])

    # Or run standalone:
    # uvicorn device_api:app --reload --port 8001
"""

import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, validator


# ==================== Pydantic Models ====================

class DeviceBase(BaseModel):
    """Base device model with shared fields"""
    device_type: str = Field(..., description="Device type: sensor / motor / controller / actuator")
    name: str = Field(..., min_length=1, max_length=100, description="Device display name")
    location: str = Field("", max_length=200, description="Physical installation location")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional device metadata")


class DeviceCreate(DeviceBase):
    """Device creation model"""
    device_id: Optional[str] = Field(None, description="Custom device ID (auto-generated if omitted)")
    status: str = Field("offline", description="Initial status: online / offline / warning / error")

    @validator("status")
    def validate_status(cls, v):
        allowed = {"online", "offline", "warning", "error"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v

    @validator("device_type")
    def validate_type(cls, v):
        allowed = {"sensor", "motor", "controller", "actuator", "gateway", "camera"}
        if v not in allowed:
            raise ValueError(f"device_type must be one of {allowed}")
        return v


class DeviceUpdate(BaseModel):
    """Device update model (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator("status")
    def validate_status(cls, v):
        if v is None:
            return v
        allowed = {"online", "offline", "warning", "error"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class DeviceBatchCreate(BaseModel):
    """Batch device creation model"""
    devices: List[DeviceCreate] = Field(..., min_items=1, max_items=500)


class DeviceBatchUpdate(BaseModel):
    """Batch device update model"""
    device_ids: List[str] = Field(..., min_items=1)
    updates: DeviceUpdate


class DeviceBatchDelete(BaseModel):
    """Batch device deletion model"""
    device_ids: List[str] = Field(..., min_items=1)


class DeviceStatusQuery(BaseModel):
    """Device status query filter"""
    status: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None


class DeviceResponse(BaseModel):
    """Device response model"""
    device_id: str
    device_type: str
    name: str
    location: str
    status: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    last_seen: Optional[str] = None


class DeviceStatusResponse(BaseModel):
    """Device status response"""
    device_id: str
    status: str
    last_seen: Optional[str] = None
    sensors: Dict[str, Optional[float]] = Field(default_factory=dict)
    actuators: Dict[str, Optional[float]] = Field(default_factory=dict)


class BatchOperationResult(BaseModel):
    """Result of a batch operation"""
    success: List[str] = Field(default_factory=list)
    failed: List[Dict[str, str]] = Field(default_factory=list)
    total_success: int = 0
    total_failed: int = 0


# ==================== In-Memory Storage (Replace with DB in production) ====================

class DeviceStore:
    """In-memory device storage with indexing. Replace with SQLite/PostgreSQL in production."""

    def __init__(self):
        self._devices: Dict[str, dict] = {}
        self._status_index: Dict[str, set] = {}  # status -> {device_ids}
        self._type_index: Dict[str, set] = {}    # type -> {device_ids}
        self._location_index: Dict[str, set] = {}  # location -> {device_ids}

    def _update_index(self, device_id: str, device: dict, old_device: dict = None):
        """Update indexes when a device is added or modified"""
        if old_device:
            # Remove from old indexes
            self._status_index.setdefault(old_device["status"], set()).discard(device_id)
            self._type_index.setdefault(old_device["device_type"], set()).discard(device_id)
            self._location_index.setdefault(old_device["location"], set()).discard(device_id)

        # Add to new indexes
        self._status_index.setdefault(device["status"], set()).add(device_id)
        self._type_index.setdefault(device["device_type"], set()).add(device_id)
        self._location_index.setdefault(device["location"], set()).add(device_id)

    def create(self, device_data: dict) -> dict:
        device_id = device_data["device_id"]
        self._devices[device_id] = device_data
        self._update_index(device_id, device_data)
        return device_data

    def get(self, device_id: str) -> Optional[dict]:
        return self._devices.get(device_id)

    def list(self, device_type: str = None, status: str = None,
             location: str = None, page: int = 1, page_size: int = 20) -> tuple:
        """List devices with filtering and pagination. Returns (devices, total_count)."""
        # Use index for fast filtering
        candidate_sets = []
        if status and status in self._status_index:
            candidate_sets.append(self._status_index[status])
        if device_type and device_type in self._type_index:
            candidate_sets.append(self._type_index[device_type])
        if location and location in self._location_index:
            candidate_sets.append(self._location_index[location])

        if candidate_sets:
            # Intersect all filter sets
            candidates = candidate_sets[0]
            for s in candidate_sets[1:]:
                candidates = candidates & s
            devices = [self._devices[did] for did in candidates if did in self._devices]
        else:
            devices = list(self._devices.values())

        total = len(devices)
        start = (page - 1) * page_size
        end = start + page_size
        return devices[start:end], total

    def update(self, device_id: str, updates: dict) -> Optional[dict]:
        device = self._devices.get(device_id)
        if not device:
            return None
        old_device = dict(device)
        device.update(updates)
        device["updated_at"] = datetime.now().isoformat()
        self._update_index(device_id, device, old_device)
        return device

    def delete(self, device_id: str) -> bool:
        if device_id not in self._devices:
            return False
        old_device = self._devices[device_id]
        del self._devices[device_id]
        self._update_index(device_id, old_device, old_device)
        # Clean up indexes
        self._status_index.setdefault(old_device["status"], set()).discard(device_id)
        self._type_index.setdefault(old_device["device_type"], set()).discard(device_id)
        self._location_index.setdefault(old_device["location"], set()).discard(device_id)
        return True

    def count(self) -> int:
        return len(self._devices)

    def count_by_status(self) -> Dict[str, int]:
        return {s: len(ids) for s, ids in self._status_index.items()}

    def count_by_type(self) -> Dict[str, int]:
        return {t: len(ids) for t, ids in self._type_index.items()}


# ==================== Initialize Store ====================

store = DeviceStore()


def _seed_demo_data():
    """Seed some demo devices for testing"""
    demo_devices = [
        {"device_id": "sensor_001", "device_type": "sensor", "name": "Temperature-Humidity Sensor #1",
         "location": "Lab A", "status": "online", "metadata": {"vendor": "DHT11", "pin": 2}},
        {"device_id": "sensor_002", "device_type": "sensor", "name": "Distance Sensor #1",
         "location": "Lab A", "status": "online", "metadata": {"vendor": "HC-SR04", "trig_pin": 9, "echo_pin": 10}},
        {"device_id": "sensor_003", "device_type": "sensor", "name": "Pressure Sensor #1",
         "location": "Lab B", "status": "warning", "metadata": {"vendor": "BMP280", "address": "0x76"}},
        {"device_id": "motor_001", "device_type": "motor", "name": "DC Motor #1",
         "location": "Lab B", "status": "online", "metadata": {"driver": "L298N", "max_speed": 255}},
        {"device_id": "servo_001", "device_type": "actuator", "name": "Servo Motor #1",
         "location": "Lab B", "status": "online", "metadata": {"range": "0-180", "pin": 6}},
        {"device_id": "controller_001", "device_type": "controller", "name": "Main Controller",
         "location": "Server Room", "status": "online", "metadata": {"board": "Arduino UNO R3"}},
        {"device_id": "sensor_004", "device_type": "sensor", "name": "Gas Sensor #1",
         "location": "Lab C", "status": "error", "metadata": {"vendor": "MQ-2", "pin": "A0"}},
        {"device_id": "gateway_001", "device_type": "gateway", "name": "Edge Gateway",
         "location": "Server Room", "status": "online", "metadata": {"cpu": "RPi 4B", "ram": "4GB"}},
    ]
    for d in demo_devices:
        now = datetime.now().isoformat()
        d["created_at"] = now
        d["updated_at"] = now
        d["last_seen"] = now
        store.create(d)


# ==================== API Router ====================

router = APIRouter()


# --- Single Device Operations ---

@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    location: Optional[str] = Query(None, description="Filter by location (partial match)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Get a paginated list of devices with optional filtering.

    - **device_type**: Filter by type (sensor, motor, controller, actuator, gateway, camera)
    - **status**: Filter by status (online, offline, warning, error)
    - **location**: Filter by location (partial match)
    - **page** / **page_size**: Pagination controls
    """
    devices, total = store.list(
        device_type=device_type,
        status=status_filter,
        location=location,
        page=page,
        page_size=page_size,
    )
    return devices


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str):
    """Get detailed information about a specific device."""
    device = store.get(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )
    return device


@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(device: DeviceCreate):
    """
    Create a new device.

    - If **device_id** is omitted, a UUID-based ID will be auto-generated.
    - Returns 409 Conflict if the device_id already exists.
    """
    device_id = device.device_id or f"dev_{uuid.uuid4().hex[:12]}"

    if store.get(device_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device '{device_id}' already exists"
        )

    now = datetime.now().isoformat()
    new_device = {
        "device_id": device_id,
        "device_type": device.device_type,
        "name": device.name,
        "location": device.location,
        "status": device.status,
        "metadata": device.metadata,
        "created_at": now,
        "updated_at": now,
        "last_seen": None,
    }
    return store.create(new_device)


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(device_id: str, update: DeviceUpdate):
    """
    Update an existing device.

    - All fields are optional; only provided fields will be updated.
    - Returns 404 if the device does not exist.
    """
    if not store.get(device_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )

    updates = {k: v for k, v in update.dict().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    updated = store.update(device_id, updates)
    return updated


@router.delete("/devices/{device_id}", status_code=status.HTTP_200_OK)
async def delete_device(device_id: str):
    """
    Delete a device.

    - Returns 404 if the device does not exist.
    """
    if not store.delete(device_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )
    return {"message": "Device deleted", "device_id": device_id}


# --- Device Status ---

@router.get("/devices/{device_id}/status", response_model=DeviceStatusResponse)
async def get_device_status(device_id: str):
    """
    Get the real-time status of a device including sensor and actuator values.

    - In production, this fetches from Redis cache or the latest MQTT payload.
    - Returns 404 if the device does not exist.
    """
    device = store.get(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )

    # In production, fetch from Redis/MQTT cache
    # Here we return a placeholder with device metadata
    return DeviceStatusResponse(
        device_id=device_id,
        status=device["status"],
        last_seen=device.get("last_seen"),
        sensors={
            "temperature": None,
            "humidity": None,
            "distance": None,
            "pressure": None,
        },
        actuators={
            "motor_speed": None,
            "servo_angle": None,
        },
    )


@router.patch("/devices/{device_id}/status")
async def update_device_status(device_id: str, new_status: str = Query(..., description="New status value")):
    """
    Update the status of a device (e.g., from online to warning).

    - Valid statuses: online, offline, warning, error
    """
    valid_statuses = {"online", "offline", "warning", "error"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    if not store.get(device_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )

    now = datetime.now().isoformat()
    store.update(device_id, {"status": new_status, "last_seen": now})
    return {"device_id": device_id, "status": new_status, "updated_at": now}


# --- Batch Operations ---

@router.post("/devices/batch/create", response_model=BatchOperationResult)
async def batch_create_devices(batch: DeviceBatchCreate):
    """
    Create multiple devices in a single request.

    - Useful for initial device provisioning.
    - Returns success and failure lists.
    """
    result = BatchOperationResult()

    for device_spec in batch.devices:
        device_id = device_spec.device_id or f"dev_{uuid.uuid4().hex[:12]}"
        if store.get(device_id):
            result.failed.append({"device_id": device_id, "error": "already exists"})
            continue

        now = datetime.now().isoformat()
        new_device = {
            "device_id": device_id,
            "device_type": device_spec.device_type,
            "name": device_spec.name,
            "location": device_spec.location,
            "status": device_spec.status,
            "metadata": device_spec.metadata,
            "created_at": now,
            "updated_at": now,
            "last_seen": None,
        }
        store.create(new_device)
        result.success.append(device_id)

    result.total_success = len(result.success)
    result.total_failed = len(result.failed)
    return result


@router.put("/devices/batch/update", response_model=BatchOperationResult)
async def batch_update_devices(batch: DeviceBatchUpdate):
    """
    Update multiple devices with the same changes.

    - Only fields provided in `updates` will be modified.
    """
    result = BatchOperationResult()
    updates = {k: v for k, v in batch.updates.dict().items() if v is not None}

    for device_id in batch.device_ids:
        if not store.get(device_id):
            result.failed.append({"device_id": device_id, "error": "not found"})
            continue
        store.update(device_id, updates)
        result.success.append(device_id)

    result.total_success = len(result.success)
    result.total_failed = len(result.failed)
    return result


@router.post("/devices/batch/delete", response_model=BatchOperationResult)
async def batch_delete_devices(batch: DeviceBatchDelete):
    """
    Delete multiple devices in a single request.
    """
    result = BatchOperationResult()

    for device_id in batch.device_ids:
        if store.delete(device_id):
            result.success.append(device_id)
        else:
            result.failed.append({"device_id": device_id, "error": "not found"})

    result.total_success = len(result.success)
    result.total_failed = len(result.failed)
    return result


# --- Statistics ---

@router.get("/devices/stats/summary")
async def device_stats_summary():
    """
    Get summary statistics about all devices.

    - Total count, count by status, count by type
    """
    return {
        "total_devices": store.count(),
        "by_status": store.count_by_status(),
        "by_type": store.count_by_type(),
        "timestamp": time.time(),
    }


@router.get("/devices/stats/by-status")
async def devices_by_status():
    """Get device counts grouped by status."""
    counts = store.count_by_status()
    return {
        "online": counts.get("online", 0),
        "offline": counts.get("offline", 0),
        "warning": counts.get("warning", 0),
        "error": counts.get("error", 0),
        "total": store.count(),
    }


@router.get("/devices/stats/by-type")
async def devices_by_type():
    """Get device counts grouped by type."""
    return store.count_by_type()


# ==================== Standalone App (for testing) ====================

app = FastAPI(
    title="Device CRUD API",
    description="Device management REST API for Digital Twin platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Import CORS for standalone mode
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the router
app.include_router(router, prefix="/api/v2", tags=["devices"])


@app.on_event("startup")
async def startup_event():
    """Seed demo data on startup"""
    _seed_demo_data()
    print(f"[DeviceAPI] Seeded {store.count()} demo devices")


@app.get("/api/health")
async def health():
    return {"status": "ok", "devices": store.count(), "timestamp": time.time()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("device_api:app", host="0.0.0.0", port=8001, reload=True)
