# Google Drive Integration Setup

This folder contains the configuration files needed for Google Drive upload functionality.

## Required Files

### 1. credentials.json
This is an OAuth 2.0 client credentials file from Google Cloud Console. It allows the application to authenticate with your Google account and upload files to your Drive.

**Setup Instructions:**

1. **Create OAuth 2.0 Credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the **Google Drive API**:
     - Go to "APIs & Services" → "Library"
     - Search for "Google Drive API"
     - Click on it and press "Enable"
   - Create OAuth 2.0 credentials:
     - Go to "APIs & Services" → "Credentials"
     - Click "Create Credentials" → "OAuth client ID"
     - If prompted, configure the OAuth consent screen:
       - Choose "External" (unless you have a Google Workspace)
       - Fill in app name (e.g., "MusePy")
       - Add your email as a test user
       - Save and continue through the steps
     - Back on credentials page, click "Create Credentials" → "OAuth client ID"
     - Choose "Desktop app" as the application type
     - Give it a name (e.g., "MusePy Desktop Client")
     - Click "Create"
   - Download the credentials:
     - Click the download button (⬇️) next to your newly created OAuth 2.0 Client ID
     - Save the JSON file
     - Rename it to `credentials.json`
     - Place it in this `google_drive/` folder

2. **Important Notes:**
   - Keep `credentials.json` secure but it's safe to bundle with your application
   - This file identifies your application, not your personal account
   - Users will authenticate with their own Google account on first run
   - See `credentials.json.template` in this folder for the expected file format

### 2. folder_id.txt
Create this file with the ID of your target Google Drive folder:

1. Open Google Drive in your browser (https://drive.google.com)
2. Create a new folder or navigate to the folder where you want recordings uploaded
3. Open the folder
4. Copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789
                                            └────────── Copy this part ────────────┘
   ```
5. Create a file named `folder_id.txt` in this `google_drive/` folder
6. Paste the folder ID into the file (no extra text, just the ID)

## Example folder_id.txt content:
```
1aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789
```

## How It Works

### First Run (Authentication)
1. When you first try to upload to Google Drive, a browser window will open
2. Sign in with your Google account
3. Grant permission for MusePy to access your Drive
4. The app saves an authentication token for future use

### Subsequent Runs
- The app uses the saved token automatically
- No browser login required
- Uploads happen in the background

### Token Storage
- **When running as script**: Token saved in `google_drive/token.json`
- **When running as executable**:
  - Windows: `C:\Users\<username>\AppData\Local\MusePy\token.json`
  - macOS: `~/Library/Application Support/MusePy/token.json`
  - Linux: `~/.config/musepy/token.json`

## File Locations

### For Development (running from Python):
```
google_drive/
├── credentials.json  (you create this - OAuth client credentials)
├── folder_id.txt     (you create this - target folder ID)
└── token.json        (auto-generated after first authentication)
```

### For Distribution (PyInstaller executable):
```
Bundled in app:
├── credentials.json  (read-only, bundled with executable)
└── folder_id.txt     (read-only, bundled with executable)

User config directory:
└── token.json        (auto-generated in user's config folder)
```

## Security Notes

- `credentials.json` identifies your application (safe to distribute)
- `token.json` contains personal access tokens (auto-generated, keep private)
- Only the `https://www.googleapis.com/auth/drive.file` scope is requested
- This scope only allows access to files created by the app

## Troubleshooting

### "credentials.json not found"
- Make sure you've downloaded and renamed the OAuth credentials file
- Place it in the `google_drive/` folder
- If building an executable, rebuild after adding the file

### "Authentication failed"
- Delete `token.json` (in config directory) and try again
- Make sure the Google Drive API is enabled in your project
- Verify your app is added to test users in the OAuth consent screen

### "Invalid folder ID"
- Check that `folder_id.txt` contains only the folder ID (no extra text)
- Verify the folder exists and is accessible to your Google account
- The folder ID is the last part of the folder's URL

### Browser doesn't open for authentication
- Check if a browser window opened in the background
- Try running the app from a terminal to see error messages
- Ensure port 0 (random port) is available for the OAuth callback

## Revoking Access

To revoke MusePy's access to your Google Drive:
1. Go to your Google Account: https://myaccount.google.com/permissions
2. Find "MusePy" in the list
3. Click "Remove Access"
4. Delete the `token.json` file from your config directory

