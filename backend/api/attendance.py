from flask import Blueprint, request, jsonify, session, send_file
import os
from datetime import datetime
import pandas as pd
from utils.db_init import get_db

bp = Blueprint('attendance', __name__)

def get_active_project():
    """Get active project for current user"""
    if 'user_id' not in session:
        return None
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, name FROM projects 
        WHERE user_id = ? AND is_active = 1
    ''', (session['user_id'],))
    
    project = cursor.fetchone()
    conn.close()
    
    return dict(project) if project else None

@bp.route('/download', methods=['GET'])
def download_attendance():
    """Download attendance Excel file"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        attendance_path = f'storage/users/{session["user_id"]}/projects/{project["id"]}/attendance/attendance.xlsx'
        
        if not os.path.exists(attendance_path):
            return jsonify({'error': 'Attendance file not found'}), 404
        
        # Send file
        return send_file(
            attendance_path,
            as_attachment=True,
            download_name=f'{project["name"]}_attendance_{datetime.now().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/today', methods=['GET'])
def today_attendance():
    """Get today's marked attendance"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        attendance_path = f'storage/users/{session["user_id"]}/projects/{project["id"]}/attendance/attendance.xlsx'
        
        if not os.path.exists(attendance_path):
            return jsonify({'marked': []}), 200
        
        df = pd.read_excel(attendance_path, engine='openpyxl')
        today = datetime.now().strftime('%Y-%m-%d')
        
        marked = []
        if today in df.columns:
            for idx, row in df.iterrows():
                if not pd.isna(row[today]) and row[today] != "":
                    marked.append({
                        'name': row["NAME"],
                        'time': row[today]
                    })
        
        return jsonify({'marked': marked}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/stats', methods=['GET'])
def attendance_stats():
    """Get attendance statistics"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        attendance_path = f'storage/users/{session["user_id"]}/projects/{project["id"]}/attendance/attendance.xlsx'
        
        if not os.path.exists(attendance_path):
            return jsonify({'error': 'Attendance file not found'}), 404
        
        df = pd.read_excel(attendance_path, engine='openpyxl')
        
        # Get date columns (exclude NAME column)
        date_columns = [col for col in df.columns if col != 'NAME']
        
        total_persons = len(df)
        total_days = len(date_columns)
        
        # Calculate attendance percentages
        attendance_data = []
        for idx, row in df.iterrows():
            present_days = sum(1 for col in date_columns 
                             if not pd.isna(row[col]) and row[col] != "")
            percentage = (present_days / total_days * 100) if total_days > 0 else 0
            
            attendance_data.append({
                'name': row['NAME'],
                'present_days': present_days,
                'total_days': total_days,
                'percentage': round(percentage, 1)
            })
        
        return jsonify({
            'total_persons': total_persons,
            'total_days': total_days,
            'attendance': attendance_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500