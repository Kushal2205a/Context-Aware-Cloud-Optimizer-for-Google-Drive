from __future__ import print_function
import os
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Google Drive scope
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

def authenticate_gdrive():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def fetch_drive_files(service):
    results = service.files().list(
        pageSize=200,
        fields="nextPageToken, files(id, name, size, mimeType, modifiedTime)"
    ).execute()
    items = results.get('files', [])
    return items

def fetch_drive_quota(service):
    about = service.about().get(fields="storageQuota").execute()
    quota = about.get('storageQuota', {})
    limit = int(quota.get('limit', 0))
    used = int(quota.get('usage', 0))
    return used, limit

def analyze_files(files):
    df = pd.DataFrame(files)
    if 'size' in df.columns:
        df['size'] = pd.to_numeric(df['size'], errors='coerce').fillna(0)
    df['modifiedTime'] = pd.to_datetime(df['modifiedTime'], errors='coerce')

    # Largest files
    largest_files = df.sort_values(by='size', ascending=False).head(5)

    # Oldest files
    oldest_files = df.sort_values(by='modifiedTime', ascending=True).head(5)

    # Duplicates
    duplicate_names = df[df.duplicated('name', keep=False)].sort_values('name')

    # File type breakdown
    df['type'] = df['mimeType'].apply(lambda x: x.split('.')[-1] if '.' in x else x.split('/')[-1])
    type_breakdown = df.groupby('type')['size'].sum().sort_values(ascending=False)

    return largest_files, oldest_files, duplicate_names, type_breakdown

def generate_recommendations(largest, oldest, duplicates):
    recs = []
    if not largest.empty:
        big_files = ", ".join([f"{row['name']} ({row['size']/(1024**2):.2f} MB)" for _, row in largest.iterrows()])
        recs.append(f"Consider deleting or compressing these large files: {big_files}")
    if not oldest.empty:
        old_files = ", ".join([f"{row['name']} (Last modified: {row['modifiedTime'].date()})" for _, row in oldest.iterrows()])
        recs.append(f"Review these old files for potential removal: {old_files}")
    if not duplicates.empty:
        dup_files = ", ".join(duplicates['name'].unique())
        recs.append(f"Remove duplicates to save space: {dup_files}")
    return recs

def main():
    st.title("Google Drive Context-Aware Optimizer")

    st.write("Authenticate to analyze your Google Drive usage.")
    creds = authenticate_gdrive()
    service = build('drive', 'v3', credentials=creds)

    # Show storage quota
    used, limit = fetch_drive_quota(service)
    if limit > 0:
        percent_used = used / limit
        st.subheader("Storage Usage")
        st.progress(percent_used)
        st.write(f"{used / (1024**3):.2f} GB of {limit / (1024**3):.2f} GB used")
    else:
        st.warning("Could not fetch storage quota.")

    files = fetch_drive_files(service)
    largest, oldest, duplicates, type_breakdown = analyze_files(files)

    # Display tables
    st.subheader("Top 5 Largest Files")
    st.table(largest[['name', 'size', 'modifiedTime']])

    st.subheader("Top 5 Oldest Files")
    st.table(oldest[['name', 'size', 'modifiedTime']])

    if not duplicates.empty:
        st.subheader("Duplicate Files")
        st.table(duplicates[['name', 'size', 'modifiedTime']])

    # Display chart
    st.subheader("Storage by File Type")
    fig, ax = plt.subplots()
    type_breakdown_mb = type_breakdown / (1024**2)
    type_breakdown_mb.plot(kind='bar', ax=ax)
    ax.set_ylabel("Size (MB)")
    ax.set_xlabel("File Type")
    st.pyplot(fig)

    # Recommendations
    st.subheader("Context-Aware Recommendations")
    recs = generate_recommendations(largest, oldest, duplicates)
    for r in recs:
        st.write(f"- {r}")

if __name__ == '__main__':
    main()
