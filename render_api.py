from flask import Flask, request, jsonify, send_file
import os
import sqlite3
import pandas as pd
from datetime import datetime
import json
import tempfile
import shutil

app = Flask(__name__)

# Configuration
CSV_DIRECTORY = os.path.join(os.path.dirname(__file__), 'csv')
USER_CSV_DIRECTORY = os.path.join(os.path.dirname(__file__), 'user_csv_files')
TEMP_IMAGE_DIRECTORY = os.path.join(os.path.dirname(__file__), 'temp_images')

# Ensure directories exist
os.makedirs(CSV_DIRECTORY, exist_ok=True)
os.makedirs(USER_CSV_DIRECTORY, exist_ok=True)
os.makedirs(TEMP_IMAGE_DIRECTORY, exist_ok=True)

@app.route('/api/status')
def api_status():
    """Check if CSV data is available"""
    csv_path = os.path.join(CSV_DIRECTORY, 'combined.csv')
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            return jsonify({
                'status': 'ready', 
                'message': 'Data available',
                'record_count': len(df),
                'last_updated': datetime.fromtimestamp(os.path.getmtime(csv_path)).isoformat()
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Data file corrupted: {str(e)}'})
    else:
        return jsonify({'status': 'not_ready', 'message': 'No data available'})

@app.route('/api/upload_data', methods=['POST'])
def upload_data():
    """Receive processed data from Discord bot"""
    try:
        data = request.get_json()
        
        # Save CSV data
        if 'csv_data' in data:
            csv_path = os.path.join(CSV_DIRECTORY, 'combined.csv')
            df = pd.DataFrame(data['csv_data'])
            df.to_csv(csv_path, index=False)
            print(f"✅ Saved CSV data with {len(df)} records")
        
        # Save user data
        if 'user_data' in data and data['user_data']:
            user_id = data.get('user_id', 'unknown')
            user_data_path = os.path.join(USER_CSV_DIRECTORY, f"user_{user_id}.csv")
            df_user = pd.DataFrame(data['user_data'])
            df_user.to_csv(user_data_path, index=False)
            print(f"✅ Saved user data for user {user_id}")
        
        return jsonify({'success': True, 'message': 'Data uploaded successfully'})
    
    except Exception as e:
        print(f"❌ Error uploading data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/process_zip', methods=['POST'])
def process_zip():
    """Process ZIP code request from Vercel"""
    try:
        data = request.get_json()
        zip_code = data.get('zip_code')
        
        # Check if data is available
        csv_path = os.path.join(CSV_DIRECTORY, 'combined.csv')
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No deal data available. Please wait for Discord bot to process data.'}), 400
        
        # Read the CSV data
        df = pd.read_csv(csv_path)
        
        if df.empty:
            return jsonify({'error': 'No deal data available'}), 400
        
        # Simple ZIP code processing (you can enhance this with your existing logic)
        # For now, we'll just return the available data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"deals_{zip_code}_{timestamp}.csv"
        
        # Create a simple filtered dataset (you can enhance this)
        filtered_df = df.copy()  # In a real implementation, you'd filter by ZIP code
        
        # Save the filtered data
        output_path = os.path.join(USER_CSV_DIRECTORY, filename)
        filtered_df.to_csv(output_path, index=False)
        
        return jsonify({
            'success': True,
            'message': f'Found {len(filtered_df)} deals for ZIP code {zip_code}',
            'filename': filename,
            'deal_count': len(filtered_df),
            'download_url': f'/api/download/{filename}'
        })
        
    except Exception as e:
        print(f"❌ Error processing ZIP: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    """Serve generated files"""
    file_path = os.path.join(USER_CSV_DIRECTORY, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'directories': {
            'csv': os.path.exists(CSV_DIRECTORY),
            'user_csv': os.path.exists(USER_CSV_DIRECTORY),
            'temp_images': os.path.exists(TEMP_IMAGE_DIRECTORY)
        }
    })

if __name__ == '__main__':
    print("🚀 Starting Render API server...")
    print(f"📁 CSV Directory: {CSV_DIRECTORY}")
    print(f"📁 User CSV Directory: {USER_CSV_DIRECTORY}")
    print(f"📁 Temp Images Directory: {TEMP_IMAGE_DIRECTORY}")
    app.run(host='0.0.0.0', port=5000, debug=True)
