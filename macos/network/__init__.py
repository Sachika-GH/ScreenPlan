"""
network module - gateway discovery, auth, and sync.
"""
from network.gateway import get_default_gateway, is_backend_reachable, get_server_url
from network.auth_manager import save_token, load_token, delete_token, save_device_id, load_device_id
from network.sync_client import (
    health_check,
    login,
    register,
    register_device,
    upload_usage,
    sync_yesterday,
    fetch_summary,
    generate_schedule,
    fetch_latest_schedule,
    get_backend_url,
    upload_timeline_event,
    save_to_offline_queue,
    flush_offline_queue,
    get_queue_size,
)
