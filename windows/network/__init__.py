"""
network package - gateway discovery, auth, and sync.
"""
from network.gateway import get_server_url, get_default_gateway, is_backend_reachable
from network.auth_manager import save_token, load_token, delete_token, save_device_id, load_device_id, save_device_identity
from network.sync_client import (
    health_check,
    login,
    register,
    register_device,
    upload_timeline_event,
    generate_schedule,
    fetch_latest_schedule,
    get_backend_url,
    save_to_offline_queue,
    flush_offline_queue,
    get_queue_size,
)
