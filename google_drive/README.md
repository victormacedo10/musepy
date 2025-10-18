# Google Drive Integration Setup

This folder contains the configuration files needed for Google Drive upload functionality.

## Required Files

### 1. service_account.json
This is a service account key file from Google Cloud Console. Service accounts allow automatic, no-login-required uploads to a specific Google Drive folder.

**Setup Instructions:**

1. **Create a Service Account:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Drive API
   - Go to "IAM & Admin" → "Service Accounts"
   - Click "Create Service Account"
   - Give it a name (e.g., "MusePy Upload Service")
   - Click "Create and Continue" → "Done"
   - Click on the service account → "Keys" tab
   - Click "Add Key" → "Create New Key" → "JSON"
   - Download the JSON key file and rename it to `service_account.json`
   - Place it in this folder

2. **Share Your Drive Folder with the Service Account:**
   - Open the downloaded JSON file and copy the `client_email` value (looks like: `your-service@project-id.iam.gserviceaccount.com`)
   - Open Google Drive in your browser
   - Navigate to the folder where you want recordings uploaded
   - Right-click the folder → "Share"
   - Paste the service account email
   - Give it "Editor" permissions
   - Click "Share"

### 2. folder_id.txt
Create this file with the ID of your target Google Drive folder:
1. Open Google Drive in your browser
2. Navigate to the folder where you want recordings to be uploaded
3. Copy the folder ID from the URL (the long string after `/folders/`)
4. Create a file named `folder_id.txt` in this folder
5. Paste the folder ID into the file (no extra text, just the ID)

## Example folder_id.txt content:
```
1aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789
```

## Benefits of Service Account Approach

- ✅ No user login required - uploads work automatically
- ✅ No browser authentication prompts
- ✅ Works on all platforms (Windows, macOS, Linux)
- ✅ Works in headless/automated environments
- ✅ All uploads go to your centralized folder
- ✅ Users never see or access your Google account

## Security Notes

- The `service_account.json` file contains credentials that allow write access to the shared folder
- Only share the specific folder with the service account, not your entire Drive
- Keep the service account key secure but note it only has access to folders you explicitly share
- If compromised, you can revoke it and create a new one in Google Cloud Console

## Troubleshooting

- Make sure the Google Drive API is enabled in your Google Cloud project
- Verify the service account email has been granted Editor access to your Drive folder
- Check that both `service_account.json` and `folder_id.txt` are in the correct location
- The app requires the `https://www.googleapis.com/auth/drive.file` scope

