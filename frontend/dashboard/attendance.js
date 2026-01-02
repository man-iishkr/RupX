// Attendance Management
// const API_BASE = "http://127.0.0.1:5000/api";
// Load data on page load
window.addEventListener('DOMContentLoaded', async () => {
    await loadTodayAttendance();
    await loadAttendanceStats();
});

// Load today's attendance
async function loadTodayAttendance() {
    try {
        const response = await fetch(`${API_BASE}/attendance/today`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        const todayList = document.getElementById('today-list');
        
        if (data.marked && data.marked.length > 0) {
            todayList.innerHTML = data.marked.map(item => `
                <div class="attendance-item">
                    <span class="attendance-name">${item.name}</span>
                    <span class="attendance-time">${item.time}</span>
                </div>
            `).join('');
        } else {
            todayList.innerHTML = `
                <p style="color: var(--text-secondary); text-align: center; padding: 2rem;">
                    No attendance marked today
                </p>
            `;
        }
    } catch (error) {
        console.error('Failed to load today\'s attendance:', error);
    }
}

// Load attendance statistics
async function loadAttendanceStats() {
    try {
        const response = await fetch(`${API_BASE}/attendance/stats`, {
            credentials: 'include'
        });
        
        if (response.status === 404) {
            // No attendance file yet
            document.getElementById('attendance-stats').style.display = 'none';
            document.getElementById('today-attendance').style.display = 'none';
            document.getElementById('no-data-message').style.display = 'block';
            return;
        }
        
        const data = await response.json();
        
        displayStats(data);
    } catch (error) {
        console.error('Failed to load stats:', error);
        document.getElementById('no-data-message').style.display = 'block';
    }
}

// Display statistics
function displayStats(data) {
    const statsDiv = document.getElementById('attendance-stats');
    
    // Calculate overall average
    const totalPresent = data.attendance.reduce((sum, person) => sum + person.present_days, 0);
    const overallAvg = data.total_days > 0 ? 
        ((totalPresent / (data.total_persons * data.total_days)) * 100).toFixed(1) : 0;
    
    statsDiv.innerHTML = `
        <div class="stat-card">
            <div class="stat-label">Total Persons</div>
            <div class="stat-value">${data.total_persons}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Total Days</div>
            <div class="stat-value">${data.total_days}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Average Attendance</div>
            <div class="stat-value">${overallAvg}%</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Today's Present</div>
            <div class="stat-value">${data.attendance.filter(p => p.present_days > 0).length}</div>
        </div>
    `;
    
    // Show detailed breakdown
    if (data.attendance.length > 0) {
        const breakdownDiv = document.createElement('div');
        breakdownDiv.style.cssText = 'grid-column: 1/-1; margin-top: 1rem;';
        breakdownDiv.innerHTML = `
            <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem;">
                <h3 style="margin-bottom: 1rem;">Individual Attendance</h3>
                <div style="display: grid; gap: 0.5rem;">
                    ${data.attendance.map(person => `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: var(--bg-hover); border-radius: 8px;">
                            <span style="font-weight: 600;">${person.name}</span>
                            <div style="display: flex; gap: 1rem; align-items: center;">
                                <span style="color: var(--text-secondary); font-size: 0.875rem;">
                                    ${person.present_days} / ${person.total_days} days
                                </span>
                                <span style="font-weight: 700; color: ${person.percentage >= 75 ? 'var(--success)' : person.percentage >= 50 ? 'var(--warning)' : 'var(--error)'};">
                                    ${person.percentage}%
                                </span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        statsDiv.appendChild(breakdownDiv);
    }
}

// Download attendance Excel
async function downloadAttendance() {
    try {
        const response = await fetch(`${API_BASE}/attendance/download`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            const data = await response.json();
            showAlert(data.error || 'Download failed', 'error');
            return;
        }
        
        // Get filename from header or use default
        const contentDisposition = response.headers.get('content-disposition');
        let filename = 'attendance.xlsx';
        
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?(.+)"?/);
            if (match) {
                filename = match[1];
            }
        }
        
        // Download file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showAlert('Attendance downloaded successfully', 'success');
    } catch (error) {
        console.error('Download error:', error);
        showAlert('Network error', 'error');
    }
}