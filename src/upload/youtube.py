import os
import json
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_FILE = "client_secret.json"
TOKEN_FILE = "token.json"

def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                logging.warning(f"{CREDENTIALS_FILE} not found. Cannot authenticate YouTube.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def upload_video(file_path, title, description, tags, privacy_status="public", thumbnail_path=None):
    youtube = get_authenticated_service()
    if not youtube:
        return False
        
    logging.info(f"Uploading {file_path} to YouTube...")
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "24" # Entertainment
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )
    
    response = None
    try:
        response = request.execute()
        video_id = response['id']
        logging.info(f"Video id '{video_id}' was successfully uploaded.")
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
                logging.info(f"Custom thumbnail uploaded for video '{video_id}'.")
            except Exception as e:
                logging.error(f"Failed to upload custom thumbnail: {e}")
                
        return video_id
    except Exception as e:
        logging.error(f"An error occurred during upload: {e}")
        return None
