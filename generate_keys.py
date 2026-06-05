from pywebpush import webpush, WebPushException
import json

# Generate VAPID keys
from pywebpush import generate_vapid_keys as generate_keys

vapid_private_key, vapid_public_key = generate_keys()

print("=" * 50)
print("COPY THESE KEYS - YOU WILL NEED THEM")
print("=" * 50)
print(f"VAPID_PUBLIC_KEY={vapid_public_key}")
print(f"VAPID_PRIVATE_KEY={vapid_private_key}")
print("=" * 50)