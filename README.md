# RupX  
**Train. Recognize. Track.**

RupX is a full-stack, AI-powered **face recognition and attendance platform** built using **ArcFace (InsightFace)**, **OpenCV**, and **Flask**.  
It allows organizations such as **colleges and offices** to train custom face recognition models, test them in real time using a browser webcam, and automatically track attendance — all within a project-based SaaS architecture.

---

## 🚀 Key Features

### 🔐 Authentication
- Email + password authentication
- SQLite-backed user management
- Secure password hashing
- One user can manage multiple projects

---

### 📦 Project-Based Architecture
- Each project has:
  - Its own dataset
  - Its own trained model (embeddings)
  - Its own attendance file
- **Maximum 5 projects per user (free tier)**
- Only **one active project** at a time
- Switching projects automatically stops recognition

---

### 🧠 Model Training (ArcFace)
- Uses **InsightFace ArcFace (buffalo_l)** model
- CPU-only inference
- Full retraining only (no incremental updates)
- Old embeddings preserved if training fails
- Enforced dataset rules:
  - Folder-per-person structure
  - Minimum **10 images per person**

---

### ⚡ Real-Time Face Recognition
- Browser webcam streaming via **WebSocket**
- Fallback MJPEG stream available
- Optimized for performance:
  - Frame skipping
  - CPU-safe inference
- Unknown faces are ignored
  - If **exactly one unknown face persists**, user is notified (informational only)

---

### 📊 Attendance Tracking
- Automatic attendance marking
- Two modes (project-level):
  - Once per day
  - Once per session
- Attendance stored in Excel format
- Editable only in downloaded version

---

### 🌐 Modern Landing Page
- Inspired by **MOSTO (Dribbble)**
- Cinematic look and feel
- 3D animated background
- Custom cursor animation
- Demo workflow:
  - Landing → Auth → Dashboard → Train → Test

---



## 🛠️ Tech Stack

### Backend
- Python
- Flask
- Flask-SocketIO
- SQLite
- InsightFace (ArcFace)
- OpenCV
- NumPy
- Pandas

### Frontend
- HTML, CSS, JavaScript
- Three.js (3D background)
- WebSocket (live video stream)

---



