import os
import io
import json
import datetime
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']


def _client_config_from_secrets():
    
    return {
        "web": {
            "client_id": st.secrets["gdrive"]["client_id"],

            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_secret": st.secrets["gdrive"]["client_secret"],
            "redirect_uris": [st.secrets["gdrive"]["redirect_uri"]],
        }
    }


def authenticate_gdrive():
    
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        return creds

    
    client_config = _client_config_from_secrets()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=st.secrets["gdrive"]["redirect_uri"],
    )

    
    qp = {}
    try:
        qp = dict(st.query_params) 
    except Exception:
        
        qp = st.experimental_get_query_params()

    if "code" in qp:
       
        code_val = qp["code"][0] if isinstance(qp["code"], list) else qp["code"]
       
        state_val = qp.get("state")
        if isinstance(state_val, list):
            state_val = state_val[0]

        
        flow.fetch_token(code=code_val)  
        creds = flow.credentials

       
        with open("token.json", "w") as token:
            token.write(creds.to_json())

        
        try:
            
            st.query_params.clear()
        except Exception:
            pass

        return creds

    
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )  

    st.markdown("To connect Google Drive, please sign in:")
    st.link_button("Sign in with Google", auth_url)

    
    st.stop()


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
