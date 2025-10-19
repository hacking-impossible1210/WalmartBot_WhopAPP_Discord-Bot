# Walmart App Deployment Guide

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Discord Bot     │    │  Render Backend │    │ Vercel Frontend │
│ (Your Computer) │    │   (API Server)  │    │   (Web App)    │
│                 │    │                 │    │                 │
│ - Discord cmds  │    │ - Data storage  │    │ - User interface│
│ - CSV processing│    │ - File serving  │    │ - ZIP lookup    │
│ - Data upload   │───▶│ - API endpoints │◀───│ - File download │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Step 1: Deploy Render Backend

### 1.1 Prepare Files
- `render_api.py` - API server
- `requirements_render.txt` - Dependencies
- `render.yaml` - Render configuration

### 1.2 Deploy to Render
1. Push code to GitHub
2. Connect GitHub repo to Render
3. Create new Web Service:
   - **Build Command**: `pip install -r requirements_render.txt`
   - **Start Command**: `python render_api.py`
   - **Environment**: Python 3.11
4. Set Environment Variables:
   - `PYTHON_VERSION=3.11.0`
   - `FLASK_ENV=production`

### 1.3 Get Render URL
- Note your Render app URL (e.g., `https://walmart-api-backend.onrender.com`)

## Step 2: Deploy Vercel Frontend

### 2.1 Prepare Files
- `whop_app.py` - Flask web app
- `requirements_vercel.txt` - Dependencies
- `vercel.json` - Vercel configuration
- `templates/index.html` - Frontend template

### 2.2 Deploy to Vercel
1. Install Vercel CLI: `npm i -g vercel`
2. Login: `vercel login`
3. Deploy: `vercel --prod`
4. Set Environment Variables:
   - `RENDER_API_URL=https://your-render-app.onrender.com`

## Step 3: Configure Local Bot

### 3.1 Environment Variables
Create `.env` file with:
```
DISCORD_BOT_TOKEN=your_bot_token
DEALS_CHANNEL_ID=your_channel_id
ZIP_CODE_CHANNEL_ID=your_zip_channel_id
STORE_ID_CHANNEL_ID=your_store_channel_id
ALLOWED_ROLES_SETZIP=role1,role2,role3
CSV_DIRECTORY=csv
ZIP_CODES_CSV=zip_codes.csv
ZIP_CODE_COORDINATES_CSV=zip_code_coordinates.csv
STORE_DATA_JSON=store_data.json
RENDER_API_URL=https://your-render-app.onrender.com
```

### 3.2 Run Bot
```bash
python bot.py
```

## Step 4: Test Integration

### 4.1 Test Discord Bot
- Upload CSV files to Discord channel
- Bot should process and upload to Render
- Use `/upload_data` command to manually sync

### 4.2 Test Web Interface
- Visit your Vercel URL
- Enter a ZIP code
- Should process through Render backend
- Download generated files

## File Structure

```
your-project/
├── bot.py                    # Discord bot (local)
├── whop_app.py              # Flask web app (Vercel)
├── render_api.py            # API server (Render)
├── requirements_render.txt   # Render dependencies
├── requirements_vercel.txt   # Vercel dependencies
├── render.yaml              # Render configuration
├── vercel.json              # Vercel configuration
├── env_template.txt         # Environment variables template
├── deployment_guide.md      # This guide
├── templates/
│   └── index.html
├── csv/                     # CSV files directory
├── user_csv_files/          # User CSV files
└── temp_images/             # Temporary images
```

## Troubleshooting

### Render Issues
- Check Render logs for errors
- Verify environment variables
- Ensure all dependencies are installed

### Vercel Issues
- Check Vercel function logs
- Verify RENDER_API_URL is set correctly
- Test API endpoints manually

### Bot Issues
- Check Discord bot token
- Verify channel IDs are correct
- Test upload functionality with `/upload_data` command

## Cost Considerations

- **Render**: Free tier (750 hours/month)
- **Vercel**: Free tier (100GB bandwidth/month)
- **Total**: $0/month for small usage

## Security Notes

- Never commit `.env` files
- Use environment variables for all secrets
- Rotate API keys regularly
- Monitor for unusual activity
