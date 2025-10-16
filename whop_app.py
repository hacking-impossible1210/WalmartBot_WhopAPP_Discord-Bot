from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

# Try to import required modules
try:
    import pandas as pd
    import sqlite3
    import pytz
    import asyncio
    import threading
    import json
    import csv
    import colorsys
    from geopy.distance import geodesic
    from fpdf import FPDF
    from PIL import Image as PILImage
    import requests
    from io import BytesIO
    DEPENDENCIES_OK = True
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please install requirements: pip install -r requirements_simple.txt")
    DEPENDENCIES_OK = False

app = Flask(__name__)

# Configuration
CSV_DIRECTORY = os.path.join(os.path.dirname(__file__), 'csv')
COMBINED_CSV_PATH = os.path.join(CSV_DIRECTORY, 'combined.csv')
USER_CSV_DIRECTORY = os.path.join(os.path.dirname(__file__), 'user_csv_files')
TEMP_IMAGE_DIRECTORY = os.path.join(os.path.dirname(__file__), 'temp_images')

# Ensure directories exist
os.makedirs(USER_CSV_DIRECTORY, exist_ok=True)
os.makedirs(TEMP_IMAGE_DIRECTORY, exist_ok=True)

# WHOP App Functions (copied from bot.py to avoid Discord dependencies)
def generate_light_colors(n):
    colors = []
    for i in range(n):
        hue = i / n
        rgb = colorsys.hsv_to_rgb(hue, 0.3, 0.95)
        hex_color = '%02x%02x%02x' % (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        colors.append(hex_color)
    return colors

def storecheck(zip_code, radius):
    """Find nearby zip codes within radius"""
    results = []
    zip_code_coordinates_csv_path = os.path.join(CSV_DIRECTORY, 'zip_code_coordinates.csv')
    
    def load_zip_code_coordinates(zip_codes_csv):
        zip_code_coords = {}
        with open(zip_codes_csv, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            next(csvreader)  # Skip header
            for row in csvreader:
                zip_code, lat, lon = row[0], float(row[1]), float(row[2])
                zip_code_coords[zip_code] = (lat, lon)
        return zip_code_coords

    def find_zip_codes_within_radius(zip_code, radius, zip_code_coords):
        origin_coords = zip_code_coords.get(zip_code)
        if not origin_coords:
            return []
        nearby_zip_codes = []
        for other_zip_code, coords in zip_code_coords.items():
            distance = geodesic(origin_coords, coords).miles
            if distance <= radius and other_zip_code != zip_code:
                nearby_zip_codes.append(other_zip_code)
        return nearby_zip_codes

    zip_code_coords = load_zip_code_coordinates(zip_code_coordinates_csv_path)
    target_zip_code = zip_code
    if radius > 50:
        radius = 50
    nearby_zip_codes = find_zip_codes_within_radius(target_zip_code, radius, zip_code_coords)
    return nearby_zip_codes

def clean_dataframe(df):
    """Clean dataframe for PDF generation"""
    def clean_text(text):
        if isinstance(text, str):
            return ''.join(char for char in text if ord(char) < 256)
        return text
    return df.applymap(clean_text)

def create_pdf_report(excel_path, pdf_path, df):
    """Create PDF report with product data"""
    pdf = FPDF(orientation='L', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Calculate dimensions
    page_width = pdf.w - 30
    img_width = 25
    row_height = 25
    remaining_width = page_width - img_width
    
    # Column widths
    col_widths = {
        'Store ID': 0.06, 'item_name': 0.15, 'MSRP': 0.05, ' Price': 0.05,
        'discount': 0.06, ' Floor Stock': 0.05, ' Backroom Stock': 0.05,
        ' In Transit Stock': 0.05, ' Aisles': 0.08, 'URL': 0.05,
        'Ebay Link': 0.06, 'UPC': 0.08, 'Address': 0.10, ' City': 0.06,
        ' State': 0.04, ' ZIP': 0.06
    }
    
    # Generate colors for stores
    unique_stores = df['Store ID'].unique()
    colors = generate_light_colors(len(unique_stores))
    store_colors = dict(zip(unique_stores, colors))
    
    # Header
    pdf.set_font("Arial", 'B', 8)
    pdf.set_fill_color(230, 230, 230)
    max_header_height = row_height
    y_start = pdf.get_y()
    x_start = pdf.get_x()
    
    # Image header
    pdf.cell(img_width, max_header_height, "Image", border=1, align='C', fill=True)
    pdf.ln(0)
    current_x = x_start + img_width
    
    # Column headers
    for col, width_ratio in col_widths.items():
        width = remaining_width * width_ratio
        pdf.set_xy(current_x, y_start)
        header_text = col.strip()
        if 'Floor Stock' in header_text:
            header_text = 'Floor'
        elif 'Backroom Stock' in header_text:
            header_text = 'Backroom'
        elif 'In Transit Stock' in header_text:
            header_text = 'In Transit'
        elif 'Ebay Link' in header_text:
            header_text = 'Ebay'
        
        pdf.cell(width, max_header_height, header_text, border=1, align='C', fill=True)
        current_x += width
    
    pdf.ln(max_header_height)
    
    # Data rows
    pdf.set_font("Arial", '', 7)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for idx, row in df.iterrows():
        row_start_y = pdf.get_y()
        
        if row_start_y + row_height > pdf.page_break_trigger:
            pdf.add_page()
            row_start_y = pdf.get_y()
        
        try:
            # Set background color
            store_id = row['Store ID']
            color = store_colors[store_id]
            r = int(color[:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:], 16)
            pdf.set_fill_color(r, g, b)
            
            # Image cell
            x_start = pdf.get_x()
            image_url = row['image_url']
            if isinstance(image_url, (int, float)):
                image_url = str(image_url)
            if image_url and image_url.strip():
                try:
                    response = requests.get(image_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        temp_img_path = os.path.join(TEMP_IMAGE_DIRECTORY, f"temp_img_{idx}.png")
                        with open(temp_img_path, 'wb') as f:
                            f.write(response.content)
                        
                        with PILImage.open(temp_img_path) as img:
                            img = img.resize((100, 100), PILImage.LANCZOS)
                            img = img.convert('RGB')
                            img.save(temp_img_path, format='PNG')
                        
                        pdf.image(temp_img_path, x=x_start + 2, y=row_start_y + 2,
                                w=img_width - 4, h=row_height - 4)
                        os.remove(temp_img_path)
                except Exception as e:
                    print(f"Image processing error: {e}")
            
            pdf.rect(x_start, row_start_y, img_width, row_height)
            pdf.set_xy(x_start + img_width, row_start_y)
            
            # Data cells
            for col, width_ratio in col_widths.items():
                width = remaining_width * width_ratio
                value = str(row.get(col, ''))
                x_pos = pdf.get_x()
                
                if col == 'UPC':
                    pdf.cell(width, row_height, 'UPC', border=1, align='C', fill=True)
                elif col in ['URL', 'Ebay Link'] and value.startswith('http'):
                    pdf.set_text_color(0, 0, 255)
                    pdf.cell(width, row_height, 'Link', border=1, align='C', fill=True, link=value.strip())
                    pdf.set_text_color(0, 0, 0)
                else:
                    if len(value) > 20 and col not in ['UPC']:
                        value = value[:17] + '...'
                    pdf.cell(width, row_height, value, border=1, align='C', fill=True)
                pdf.set_xy(x_pos + width, row_start_y)
            
            pdf.ln(row_height)
            
        except Exception as e:
            print(f"Error processing row: {e}")
            continue
    
    pdf.output(pdf_path)

@app.route('/')
def index():
    """Main page with ZIP code input form"""
    if not DEPENDENCIES_OK:
        return """
        <html>
        <head><title>Dependencies Missing</title></head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1>❌ Dependencies Missing</h1>
            <p>Please install required packages:</p>
            <pre style="background: #f0f0f0; padding: 20px; border-radius: 5px;">
pip install -r requirements_simple.txt
            </pre>
            <p>Then restart the application.</p>
        </body>
        </html>
        """
    return render_template('index.html')

@app.route('/process_zip', methods=['POST'])
def process_zip():
    """Process ZIP code and generate PDF"""
    if not DEPENDENCIES_OK:
        return jsonify({'error': 'Dependencies not installed. Please install requirements.'}), 500
    
    try:
        zip_code = request.form.get('zip_code', '').strip()
        
        if not zip_code or len(zip_code) != 5 or not zip_code.isdigit():
            return jsonify({'error': 'Please enter a valid 5-digit ZIP code'}), 400
        
        # Process the ZIP code using the same logic as the Discord bot
        result = process_zip_code(zip_code)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Found {result["deal_count"]} deals for ZIP code {zip_code}',
                'download_url': result['pdf_url'],
                'deal_count': result['deal_count']
            })
        else:
            return jsonify({'error': result['message']}), 400
            
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

def process_zip_code(zip_code):
    """Process ZIP code and generate PDF using bot logic"""
    try:
        # Load the combined CSV file
        if not os.path.exists(COMBINED_CSV_PATH):
            return {'success': False, 'message': 'No deal data available. Please try again later.'}
        
        combined_df = pd.read_csv(COMBINED_CSV_PATH, dtype={' ZIP': str, 'Store ID': str})
        
        # Ensure ZIP codes are compared as strings
        combined_df[' ZIP'] = combined_df[' ZIP'].astype(str).str.strip().str.split('.').str[0]
        
        # Find nearby ZIP codes within 50 miles
        radius = 50
        nearby_zip_codes = storecheck(zip_code, radius)
        nearby_zip_codes = [str(z).strip().split('.')[0] for z in nearby_zip_codes]
        
        # Convert discount column
        def convert_discount(x):
            try:
                return int(x.rstrip('%'))
            except (ValueError, AttributeError):
                return 0
        
        combined_df['discount'] = combined_df['discount'].apply(convert_discount)
        
        # Convert stock columns to numeric
        stock_columns = [' Floor Stock', ' Backroom Stock', ' In Transit Stock']
        for col in stock_columns:
            combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').fillna(0).astype(int)
        
        # Filter deals
        filtered_df = combined_df[
            (combined_df[' ZIP'].str[:5].isin([z[:5] for z in nearby_zip_codes])) &
            (combined_df['discount'] >= 50) &
            (
                (combined_df[' Floor Stock'] > 1) |
                (combined_df[' Backroom Stock'] > 1) |
                (combined_df[' In Transit Stock'] > 1)
            )
        ]
        
        if filtered_df.empty:
            return {'success': False, 'message': 'No deals found within 50 miles of your ZIP code.'}
        
        # Generate files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'deals_{zip_code}_{timestamp}.csv'
        excel_filename = f'deals_{zip_code}_{timestamp}.xlsx'
        pdf_filename = f'deals_{zip_code}_{timestamp}.pdf'
        
        csv_path = os.path.join(USER_CSV_DIRECTORY, csv_filename)
        excel_path = os.path.join(USER_CSV_DIRECTORY, excel_filename)
        pdf_path = os.path.join(USER_CSV_DIRECTORY, pdf_filename)
        
        # Save CSV
        filtered_df.to_csv(csv_path, index=False)
        
        # Process data for Excel and PDF
        df = filtered_df.copy()
        df = df[df['discount'] != 100]
        
        if 'discount' in df.columns:
            df['discount'] = df['discount'].astype(str) + '%'
            df['discount'] = df['discount'].str.rstrip('%').astype(float)
        
        # Sort and remove duplicates
        df = df.sort_values(['Store ID', 'discount'], ascending=[True, False])
        df = df.drop_duplicates(subset=['Store ID', 'item_name'], keep='first')
        
        # Replace MSRP of 0 with 'N/A'
        df['MSRP'] = df['MSRP'].apply(lambda x: 'N/A' if float(x) == 0 else x)
        
        # Create eBay links
        df['Ebay Link'] = df['item_name'].astype(str).apply(
            lambda x: f"https://www.ebay.com/sch/i.html?_nkw={x.replace(' ', '+')}&_sacat=0&rt=nc&LH_Sold=1&LH_Complete=1"
        )
        
        # Sort data
        df = df.sort_values(['Store ID', 'discount'], ascending=[True, False])
        df['discount'] = df['discount'].astype(str) + '%'
        
        # Save Excel
        df.to_excel(excel_path, index=False)
        
        # Generate PDF
        df_cleaned = clean_dataframe(df)
        create_pdf_report(excel_path, pdf_path, df_cleaned)
        
        return {
            'success': True,
            'deal_count': len(df),
            'pdf_url': f'/download/{pdf_filename}',
            'csv_url': f'/download/{csv_filename}',
            'excel_url': f'/download/{excel_filename}'
        }
        
    except Exception as e:
        return {'success': False, 'message': f'Error processing ZIP code: {str(e)}'}

@app.route('/download/<filename>')
def download_file(filename):
    """Serve files for download"""
    try:
        file_path = os.path.join(USER_CSV_DIRECTORY, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error downloading file: {str(e)}'}), 500

@app.route('/view/<filename>')
def view_file(filename):
    """View PDF files in browser"""
    try:
        file_path = os.path.join(USER_CSV_DIRECTORY, filename)
        if os.path.exists(file_path) and filename.endswith('.pdf'):
            return send_file(file_path, mimetype='application/pdf')
        else:
            return jsonify({'error': 'File not found or not a PDF'}), 404
    except Exception as e:
        return jsonify({'error': f'Error viewing file: {str(e)}'}), 500

@app.route('/status')
def status():
    """Check if the system is ready"""
    try:
        # Check if combined CSV exists
        csv_exists = os.path.exists(COMBINED_CSV_PATH)
        
        # Check CSV file age
        csv_age = None
        if csv_exists:
            csv_mtime = os.path.getmtime(COMBINED_CSV_PATH)
            csv_age = datetime.fromtimestamp(csv_mtime)
        
        return jsonify({
            'status': 'ready' if csv_exists else 'no_data',
            'csv_exists': csv_exists,
            'csv_age': csv_age.isoformat() if csv_age else None,
            'message': 'System ready' if csv_exists else 'No deal data available'
        })
    except Exception as e:
        return jsonify({'error': f'Status check failed: {str(e)}'}), 500

if __name__ == '__main__':
    print("🛒 Starting Walmart Deals WHOP App...")
    print("📱 Web interface will be available at: http://localhost:5000")
    print("🔗 Users can enter ZIP codes to get personalized deal reports")
    print("📄 Reports include PDF, Excel, and CSV formats")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
    except Exception as e:
        print(f"❌ Error starting WHOP app: {e}")
        print("Try running: python start_whop.py")
