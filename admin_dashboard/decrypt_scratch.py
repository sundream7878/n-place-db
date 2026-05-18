import hashlib, uuid, base64

def get_hwid():
    node_id = str(uuid.getnode())
    return hashlib.sha256(node_id.encode()).hexdigest()[:16].upper()

def decrypt(enc, key):
    try:
        data = base64.b64decode(enc)
        key_bytes = key.encode('utf-8')
        res = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data)])
        return res.decode('utf-8')
    except Exception as e:
        return f"Error: {e}"

hwid = get_hwid()
print(f"HWID: {hwid}")
print(f"Email PW: {decrypt('EgtnchEecg0BZGxi', hwid)}")
print(f"Insta PW: {decrypt('KCxRKSh+DnkKGg==', hwid)}")
