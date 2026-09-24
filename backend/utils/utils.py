import os

def get_session_dir(session_id: str):
    path = os.path.join("reports", session_id)
    os.makedirs(path, exist_ok=True) 
    return path