import os
import io
import datetime
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

# Load secrets from Streamlit's secure storage
CLIENT_ID = st.secrets["gdrive"]["client_id"]
CLIENT_SECRET = st.secrets["gdrive"]["client_secret"]
REDIRECT_URI = st.secrets["gdrive"]["redirect_uri"]

def authenticate_gdrive():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_dict = {
                "installed": {
                    "client_id": st.secrets["gdrive"]["client_id"],
                    "client_secret": st.secrets["gdrive"]["client_secret"],
                    "redirect_uris": [st.secrets["gdrive"]["redirect_uri"]],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            with open("temp_credentials.json", "w") as f:
                json.dump(creds_dict, f)

            flow = InstalledAppFlow.from_client_secrets_file("temp_credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def list_files(service):
    results = service.files().list(
        pageSize=100,
        fields="files(id, name, size, modifiedTime)"
    ).execute()
    return results.get("files", [])

def get_storage_usage(service):
    about = service.about().get(fields="storageQuota").execute()
    limit = int(about["storageQuota"]["limit"])
    usage = int(about["storageQuota"]["usage"])
    return usage, limit

def analyze_files(files):
    df = pd.DataFrame(files)
    df["size"] = pd.to_numeric(df["size"], errors="coerce").fillna(0)
    df["modifiedTime"] = pd.to_datetime(df["modifiedTime"], errors="coerce")

    largest_files = df.sort_values("size", ascending=False).head(5)
    oldest_files = df.sort_values("modifiedTime").head(5)
    duplicates = df[df.duplicated(subset=["name"], keep=False)]

    return largest_files, oldest_files, duplicates

def plot_storage(usage, limit):
    fig, ax = plt.subplots()
    ax.bar(["Used", "Free"], [usage, limit - usage], color=["red", "green"])
    ax.set_ylabel("Bytes")
    ax.set_title("Google Drive Storage Usage")
    st.pyplot(fig)

def main():
    st.title("Context-Aware Cloud Optimizer for Google Drive")
    st.write("Analyze your Google Drive storage and get cleanup recommendations.")

    creds = authenticate_gdrive()
    service = build("drive", "v3", credentials=creds)

    usage, limit = get_storage_usage(service)
    st.subheader("Storage Usage")
    st.write(f"**Used:** {usage / (1024**3):.2f} GB / {limit / (1024**3):.2f} GB")
    plot_storage(usage, limit)

    files = list_files(service)
    largest, oldest, duplicates = analyze_files(files)

    st.subheader("Top 5 Largest Files")
    st.dataframe(largest[["name", "size"]])

    st.subheader("Top 5 Oldest Files")
    st.dataframe(oldest[["name", "modifiedTime"]])

    st.subheader("Duplicate Files")
    st.dataframe(duplicates[["name", "size"]])

    st.subheader("Context-Aware Recommendations")
    if not largest.empty:
        st.write(f"Consider removing large files like: {', '.join(largest['name'].head(3))}")
    if not oldest.empty:
        st.write(f"Review old files such as: {', '.join(oldest['name'].head(3))}")
    if not duplicates.empty:
        st.write("Remove duplicate files to free space.")

if __name__ == "__main__":
    main()
