import subprocess
import sys
import json

# Try to install the vapid key generator
try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    import base64
    
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    
    private_numbers = private_key.private_numbers()
    public_numbers = public_key.public_numbers()
    
    # Convert to bytes
    private_value = private_numbers.private_value.to_bytes(32, 'big')
    public_x = public_numbers.x.to_bytes(32, 'big')
    public_y = public_numbers.y.to_bytes(32, 'big')
    public_bytes = b'\x04' + public_x + public_y
    
    vapid_private_key = base64.urlsafe_b64encode(private_value).decode().rstrip('=')
    vapid_public_key = base64.urlsafe_b64encode(public_bytes).decode().rstrip('=')
    
    print("=" * 50)
    print("COPY THESE KEYS - YOU WILL NEED THEM")
    print("=" * 50)
    print(f"VAPID_PUBLIC_KEY={vapid_public_key}")
    print(f"VAPID_PRIVATE_KEY={vapid_private_key}")
    print("=" * 50)
    
except Exception as e:
    print(f"Error: {e}")
    print("\nTry installing: pip install cryptography")