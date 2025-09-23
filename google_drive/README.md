# Google Drive Integration Setup

This folder contains the configuration files needed for Google Drive upload functionality.

## Required Files

### 1. credentials.json
Download this file from the Google Cloud Console:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API
4. Go to "Credentials" and create "OAuth 2.0 Client IDs"
5. Download the JSON file and rename it to `credentials.json`
6. Place it in this folder

### 2. folder_id.txt
Create this file with the ID of your target Google Drive folder:
1. Open Google Drive in your browser
2. Navigate to the folder where you want recordings to be uploaded
3. Copy the folder ID from the URL (the long string after `/folders/`)
4. Create a file named `folder_id.txt` in this folder
5. Paste the folder ID into the file (no extra text, just the ID)

## Optional Files

### token.json
This file is automatically created after the first successful authentication and contains your access tokens. Do not share this file as it contains sensitive authentication information.

## Example folder_id.txt content:
```
1aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789
```

## Troubleshooting

- If you get authentication errors, delete `token.json` and try again
- Make sure the Google Drive API is enabled in your Google Cloud project
- Ensure the OAuth consent screen is properly configured
- The app requires the `https://www.googleapis.com/auth/drive.file` scope
