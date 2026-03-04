"""
Attendance API - Rewritten to use attendance_records database table.
Previously read from local .xlsx files which disappear on server restarts.
"""

from flask import Blueprint, request, jsonify, session, send_file
import os
import io
from datetime import datetime
import pandas as pd
from utils.db import get_db

bp = Blueprint('attendance', __name__)


def get_active_project():
    """Get active project for current user"""
    if 'user_id' not in session:
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, name, attendance_names
        FROM projects
        WHERE user_id = ? AND is_active = 1
    ''', (session['user_id'],))

    project = cursor.fetchone()
    conn.close()

    return dict(project) if project else None


def get_all_records(project_id):
    """Fetch all attendance records for a project from the DB."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, marked_at, session_id
        FROM attendance_records
        WHERE project_id = ?
        ORDER BY marked_at ASC
    ''', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@bp.route('/today', methods=['GET'])
def today_attendance():
    """Get today's marked attendance from DB"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400

    try:
        today = datetime.now().strftime('%Y-%m-%d')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, marked_at
            FROM attendance_records
            WHERE project_id = ? AND session_id = ?
            ORDER BY marked_at ASC
        ''', (project['id'], today))
        rows = cursor.fetchall()
        conn.close()

        marked = []
        for row in rows:
            r = dict(row)
            # Parse time from ISO datetime string
            try:
                dt = datetime.fromisoformat(r['marked_at'])
                time_str = dt.strftime('%I:%M %p')
            except Exception:
                time_str = r['marked_at']
            marked.append({'name': r['name'], 'time': time_str})

        return jsonify({'marked': marked}), 200

    except Exception as e:
        print(f"Error fetching today attendance: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/stats', methods=['GET'])
def attendance_stats():
    """Get attendance statistics from DB"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400

    try:
        records = get_all_records(project['id'])

        if not records:
            return jsonify({
                'total_persons': 0,
                'total_days': 0,
                'attendance': []
            }), 200

        # Build a pivot: person -> set of dates present
        from collections import defaultdict
        person_dates = defaultdict(set)
        all_dates = set()

        for rec in records:
            try:
                day = rec['session_id'] or rec['marked_at'][:10]
            except Exception:
                day = datetime.now().strftime('%Y-%m-%d')
            person_dates[rec['name']].add(day)
            all_dates.add(day)

        total_days = len(all_dates)

        # Include names from training even if never present
        trained_names = []
        if project.get('attendance_names'):
            import json
            try:
                trained_names = json.loads(project['attendance_names'])
            except Exception:
                pass

        all_names = set(person_dates.keys()) | set(trained_names)

        attendance_data = []
        for name in sorted(all_names):
            present_days = len(person_dates.get(name, set()))
            percentage = (present_days / total_days * 100) if total_days > 0 else 0
            attendance_data.append({
                'name': name,
                'present_days': present_days,
                'total_days': total_days,
                'percentage': round(percentage, 1)
            })

        return jsonify({
            'total_persons': len(all_names),
            'total_days': total_days,
            'attendance': attendance_data
        }), 200

    except Exception as e:
        print(f"Error fetching attendance stats: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/download', methods=['GET'])
def download_attendance():
    """Generate and download attendance Excel file from DB"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400

    try:
        import json
        from collections import defaultdict

        records = get_all_records(project['id'])

        # Build pivot table: rows = persons, cols = dates, cells = time marked
        person_dates = defaultdict(dict)
        all_dates = set()

        for rec in records:
            name = rec['name']
            day = rec.get('session_id') or rec['marked_at'][:10]
            try:
                dt = datetime.fromisoformat(rec['marked_at'])
                time_str = dt.strftime('%H:%M')
            except Exception:
                time_str = 'Present'

            person_dates[name][day] = time_str
            all_dates.add(day)

        sorted_dates = sorted(all_dates)

        # Include all trained persons
        trained_names = []
        if project.get('attendance_names'):
            try:
                trained_names = json.loads(project['attendance_names'])
            except Exception:
                pass

        all_names = sorted(set(person_dates.keys()) | set(trained_names))

        if not all_names:
            return jsonify({'error': 'No attendance data to export'}), 404

        data_rows = []
        for name in all_names:
            row = {'NAME': name}
            for date in sorted_dates:
                row[date] = person_dates[name].get(date, '')
            data_rows.append(row)

        df = pd.DataFrame(data_rows, columns=['NAME'] + sorted_dates)

        # Write to in-memory bytes buffer (no local fs needed)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance')

        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'{project["name"]}_attendance_{datetime.now().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"Error generating attendance: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/records', methods=['GET'])
def all_records():
    """Get all attendance records from DB"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400

    try:
        records = get_all_records(project['id'])
        return jsonify({'records': records}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500