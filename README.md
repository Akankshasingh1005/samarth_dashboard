<div align="center">

<img src="logo.jpeg" alt="SAMARTH Logo" width="160" />

# SAMARTH

### Smart Augmented Mobility & Adaptive Rehabilitation Technologies for Humans

**An AI-guided physiotherapy rehabilitation platform for real-time biomechanical analysis, kinematic monitoring, and clinical outcome tracking**

*Developed at IIT (BHU) Varanasi - Physiotherapy · Machine Learning · Impact*

---

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript)](https://www.typescriptlang.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=flat-square&logo=mongodb)](https://mongodb.com)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Pose-0097A7?style=flat-square&logo=google)](https://mediapipe.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [How It Works](#how-it-works)
4. [Technology Stack](#technology-stack)
5. [Database Design](#database-design)
6. [WebSocket Protocol](#websocket-protocol)
7. [Pipeline Modules (PS1 / PS2 / PS3)](#pipeline-modules)
8. [API Reference](#api-reference)
9. [Repository Structure](#repository-structure)
10. [Installation & Setup](#installation--setup)
11. [Environment Variables](#environment-variables)
12. [Docker Deployment](#docker-deployment)
13. [Integrating PS2 and PS3](#integrating-ps2-and-ps3)

---

## Overview

SAMARTH is a full-stack, real-time physiotherapy rehabilitation platform that fuses **computer vision**, **biomechanical kinematics**, and **clinical data management** into a single cohesive system. It is designed for use in hospitals, clinics, and home-based telerehabilitation settings.

The system enables:

- **Patients** to perform assigned rehabilitation exercises under real-time AI supervision, receiving instant form feedback without any wearable hardware.
- **Therapists** to remotely monitor patient adherence, review biomechanical analytics across sessions, and generate clinical PDF reports.
- **Researchers** to plug in ML models (PS2) and embedded sensor firmware (PS3) through clearly defined integration contracts without touching the core platform.

The platform is built around the team's **PS1 KinemaFlow** computer vision pipeline as its primary sensing engine, with purpose-built adapter layers for the upcoming PS2 (exercise analysis ML model) and PS3 (BLE/IMU wearable sensor) modules.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Patient Browser                            │
│  React 18 + TypeScript  ·  Vite 5  ·  Tailwind CSS  ·  Recharts   │
│                                                                     │
│   Camera Feed ──► MediaStream API ──► JPEG Frames                  │
│   WebSocket Client (live session + camera validation)              │
│   REST Client (axios, /api/v1/*)                                   │
└────────────────────────┬───────────────────┬────────────────────────┘
                         │ HTTP / WS         │ HTTP / WS
                         ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Uvicorn/ASGI)                  │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  REST Routes │  │  WS Handlers │  │  Auth (JWT HS256)        │  │
│  │  /api/v1/*   │  │  /ws/session │  │  Access + Refresh Tokens │  │
│  │              │  │  /ws/camera  │  │                          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────┘  │
│         │                 │                                         │
│         ▼                 ▼                                         │
│  ┌──────────────────────────────────────────────┐                  │
│  │           PoseEngineAdapter (Singleton)       │                  │
│  │  The ONLY gateway to the PS1 pipeline.        │                  │
│  │  Manages per-session PoseEstimator lifecycle. │                  │
│  └──────────────────┬───────────────────────────┘                  │
│                     │ sys.path injection                            │
└─────────────────────┼───────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   PS1 - KinemaFlow Pipeline                         │
│                                                                     │
│  BackgroundSegmenter  ·  VideoEnhancer  ·  PoseEstimator (MP)      │
│  KinematicsExtractor  ·  FeatureExtractor  ·  FilterUtils          │
│                                                                     │
│  Real-time mode: per-JPEG-frame inference                          │
│  Batch mode:     run_pipeline_on_video() → CSV + angle timeseries  │
└─────────────────────────────────────────────────────────────────────┘
                      │
         ┌────────────┴──────────────┐
         ▼                           ▼
┌─────────────────┐       ┌─────────────────────┐
│ PS2 (stub)      │       │ PS3 (stub)          │
│ ML Exercise     │       │ BLE/IMU Sensor Hub  │
│ Analyzer        │       │                     │
│ model_analyzer  │       │ mock_sensor.py      │
│ .py             │       │ → real firmware     │
└─────────────────┘       └─────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  MongoDB Atlas (Motor + Beanie) │
│  14 document collections        │
└─────────────────────────────────┘
```

---

## How It Works

### 1. Camera Validation (Pre-Session)

Before every exercise session, the patient enters the **Camera Validation** screen. This screen opens a dedicated WebSocket channel (`/ws/camera/{token}`) and begins streaming JPEG frames from the browser's webcam to the backend at approximately 10–15 fps.

The `PoseEngineAdapter` runs PS1's `PoseEstimator` on each frame and evaluates **10 real-time checks**:

| Check | Description |
|---|---|
| Left hip visible | Landmark visibility ≥ 0.5 threshold |
| Right hip visible | Landmark visibility ≥ 0.5 threshold |
| Left knee visible | Landmark visibility ≥ 0.5 threshold |
| Right knee visible | Landmark visibility ≥ 0.5 threshold |
| Left ankle visible | Landmark visibility ≥ 0.5 threshold |
| Right ankle visible | Landmark visibility ≥ 0.5 threshold |
| Full lower body visible | All six landmarks above passing simultaneously |
| Inside exercise zone | Hip X-position within 15–85% of frame width; body height fraction ≥ 35% |
| Adequate lighting | Mean luminance of grayscale frame ≥ 50 |
| Camera stable | Frame-to-frame landmark drift < 0.08 normalised units |

Only when **all 10 checks pass** is the patient allowed to proceed. The frontend renders a live checklist that updates per-frame, with a textual guidance message telling the patient exactly what to correct.

### 2. Live Exercise Session

Once validated, a second WebSocket connection (`/ws/session/{session_id}/{token}`) is opened. The patient performs their assigned exercise in front of the camera.

**Data flow per frame:**

```
Browser Webcam
  → canvas.toDataURL('image/jpeg')
  → base64-encode
  → JSON {type: "frame", data: "<base64>"}
  → WebSocket send
  → Backend receives → base64-decode → JPEG bytes
  → cv2.imdecode → numpy array
  → PS1 PoseEstimator.process_frame(frame)
  → PS1 KinematicsExtractor.extract_angles(joints)
  → FrameAngles {left_knee, right_knee, left_hip, right_hip, left_ankle, right_ankle}
  → Rep counter (knee flexion peak detection)
  → JSON response → WebSocket send → Frontend
```

The frontend renders:
- **Live angle gauges** for 6 joints (degrees)
- **Rep counter** with peak-detection logic
- **Pose confidence** indicator (mean landmark visibility)
- **RehabNet PS2 feedback** when `PS2_MODEL_PATH` is configured, with fallback mock feedback if the model is unavailable

### 3. Batch Video Upload

Alternatively, patients can upload a pre-recorded video. The backend validates the file, extracts readable frame metadata, then runs PS1 batch processing with video enhancement, background handling, pose estimation, kinematics, repetition detection, and annotated video generation. The PS1 output is passed to RehabNet PS2 for movement-quality analysis.

The upload flow returns:
- Per-frame angle time-series CSV
- Exercise summary CSV
- Rep segmentation with symmetry metrics
- Bilateral ROM averages
- PS2 error flags, confidence values, quality score, trend, and recommendations
- Annotated video URL when overlay generation succeeds

Results are stored in MongoDB and visualised on the Analytics dashboard.

### 4. Clinical Analytics

Therapists view per-patient dashboards showing:
- ROM recovery trend (left vs right, by week)
- Bilateral symmetry index over time
- Exercise compliance rate
- Session-level PS2 error breakdowns
- PDF clinical reports (generated server-side via WeasyPrint)

---

## Technology Stack

### Backend

| Technology | Version | Role |
|---|---|---|
| **Python** | 3.10+ | Primary backend language |
| **FastAPI** | 0.111 | Async REST + WebSocket framework (ASGI) |
| **Uvicorn** | 0.29 | ASGI server with WebSocket support |
| **Motor** | 3.7.1 | Async MongoDB driver (non-blocking I/O) |
| **Beanie** | 1.26 | MongoDB ODM - document models with Pydantic V2 |
| **Pydantic** | 2.7 | Request/response validation and settings management |
| **python-jose** | 3.3 | JWT token creation and verification (HS256) |
| **passlib[bcrypt]** | 1.7 | Password hashing (bcrypt) |
| **MediaPipe** | 0.10.14 | Google's pose estimation model (33 keypoints) |
| **OpenCV** | 4.9 | Frame decoding, image processing, luminance analysis |
| **NumPy** | 1.26 | Landmark array processing, angle computation |
| **SciPy** | 1.13 | Signal filtering (Butterworth, Savitzky-Golay) |
| **Pandas** | 2.2 | Time-series CSV export |
| **WeasyPrint** | 62.3 | Server-side PDF report generation |
| **Cloudinary** | 1.40 | Optional cloud video/image storage (production) |
| **Loguru** | 0.7 | Structured logging |

### Frontend

| Technology | Version | Role |
|---|---|---|
| **React** | 18 | UI component framework |
| **TypeScript** | 5 | Type-safe application code |
| **Vite** | 5.4 | Build tool with HMR dev server and proxy |
| **Tailwind CSS** | 3 | Utility-first CSS framework |
| **Recharts** | 2 | Declarative chart library (ROM trends, compliance) |
| **Zustand** | 4 | Lightweight global state management (auth store) |
| **React Router** | 6 | Client-side navigation |
| **Axios** | 1.7 | HTTP client with interceptors for token refresh |
| **Lucide React** | 0.441 | Icon system (replaces all emoji) |
| **Sonner** | 1 | Toast notification system |
| **WebSocket API** | Native | Browser-native WebSocket for live sessions |
| **MediaStream API** | Native | Browser webcam capture (`getUserMedia`) |

### Infrastructure

| Technology | Role |
|---|---|
| **MongoDB Atlas** | Managed cloud database (free tier supported) |
| **Docker + Docker Compose** | Containerised development and deployment |
| **Vite Proxy** | Dev-time HTTP/WS forwarding from `:5173` → `:8000` |

---

## Database Design

SAMARTH uses **MongoDB** with **Motor** (async driver) and **Beanie** (ODM). All collections are schema-validated at the application layer via Pydantic V2 models.

### Collections

| Collection | Document Model | Description |
|---|---|---|
| `users` | `User` | Authentication records - email, bcrypt hash, role (`patient`\|`therapist`), JWT timestamps |
| `patients` | `Patient` | Patient profile - linked `user_id`, diagnosis, therapist assignment, compliance rate |
| `therapists` | `Therapist` | Therapist profile - linked `user_id`, specialisation, patient list |
| `exercises` | `Exercise` | Exercise library - name, category, target ROM (degrees), target reps/sets, safety instructions, contraindications |
| `exercise_plans` | `ExercisePlan` | Therapist-assigned plans - list of exercises, frequency, start/end date |
| `sessions` | `Session` | Per-exercise-session record - mode (`live`\|`upload`\|`sensor`), status, duration, total reps, ROM averages, symmetry score |
| `pose_data` | `PoseData` | Raw per-frame landmark dump (33 keypoints × `x,y,z,visibility`) - linked to session |
| `angle_data` | `AngleData` | Computed joint angles per frame - left/right knee, hip, ankle (degrees) - linked to session |
| `uploaded_videos` | `UploadedVideo` | Video upload metadata - filename, storage URL, PS1 processing status |
| `feedback_events` | `FeedbackEvent` | Real-time PS2 form-error events - flag type, rep index, severity |
| `analytics` | `AnalyticsSnapshot` | Aggregated weekly analytics - ROM averages, compliance, rep totals, symmetry index |
| `reports` | `Report` | Generated PDF/CSV report records - type, file URL, date range |
| `notifications` | `Notification` | In-app notifications - type, message, read status, linked patient |
| `system_logs` | `SystemLog` | Structured audit log - action, actor, resource, timestamp |

### Key Relationships

```
User ──< Patient ──< Session ──< AngleData
                            ──< PoseData
                            ──< FeedbackEvent
                            ──< UploadedVideo
     ──< Therapist ──< ExercisePlan ──< Exercise
                   ──< Patient (assigned)
Patient ──< AnalyticsSnapshot
        ──< Report
        ──< Notification
```

### Indexing Strategy

- `users`: unique index on `email`
- `sessions`: compound index on `(patient_id, created_at DESC)`
- `angle_data`: index on `session_id`
- `analytics`: compound index on `(patient_id, week_start)`

---

## WebSocket Protocol

SAMARTH uses **two persistent WebSocket channels**, both authenticated via JWT token in the URL path (avoiding cookie complexity in WebSocket handshakes).

### Channel 1 - Camera Validation

```
Endpoint: ws://localhost:8000/ws/camera/{jwt_access_token}
Purpose:  Pre-session camera positioning check
Timeout:  15 seconds of inactivity
```

**Client → Server:**
```json
{ "type": "frame",  "data": "<base64-encoded JPEG>" }
{ "type": "ping" }
{ "type": "stop" }
```

**Server → Client:**
```json
{
  "type": "validation",
  "frame_index": 42,
  "pose_confidence": 0.87,
  "validation": {
    "left_hip_visible": true,
    "right_hip_visible": true,
    "left_knee_visible": true,
    "right_knee_visible": true,
    "left_ankle_visible": false,
    "right_ankle_visible": false,
    "full_lower_body_visible": false,
    "inside_zone": false,
    "adequate_lighting": true,
    "camera_stable": true,
    "all_valid": false,
    "guidance_message": "Move back - ankles not visible. Ensure feet are in frame"
  },
  "landmarks": {
    "LEFT_HIP":   { "x_norm": 0.48, "y_norm": 0.52, "visibility": 0.97 },
    "RIGHT_HIP":  { "x_norm": 0.55, "y_norm": 0.53, "visibility": 0.96 },
    "LEFT_KNEE":  { "x_norm": 0.47, "y_norm": 0.72, "visibility": 0.91 }
  }
}
```

### Channel 2 - Live Exercise Session

```
Endpoint: ws://localhost:8000/ws/session/{session_id}/{jwt_access_token}
Purpose:  Per-frame pose inference + rep counting during active exercise
Timeout:  30 seconds of inactivity
```

**Client → Server:**
```json
{ "type": "frame", "data": "<base64-encoded JPEG>" }
{ "type": "ping" }
{ "type": "end" }
```

**Server → Client (per frame):**
```json
{
  "type": "frame_result",
  "frame_index": 150,
  "timestamp_ms": 1717843200000,
  "pose_confidence": 0.91,
  "rep_count": 5,
  "angles": {
    "left_knee":  112.4,
    "right_knee": 109.8,
    "left_hip":   95.2,
    "right_hip":  93.7,
    "left_ankle": 88.1,
    "right_ankle": 87.6
  },
  "validation": { "...": "same structure as camera validation" },
  "landmarks": { "...": "normalised x,y + visibility per joint" }
}
```

**Rep Detection Algorithm:**

The backend uses a simple flexion-peak detector on the knee angle signal:
```python
# Knee flexion = 180° - knee_angle
# A rep is counted when:
# 1. flexion_history[-2] > flexion_history[-1]   (descending)
# 2. flexion_history[-2] > flexion_history[-3]   (was ascending)
# 3. Peak flexion > 15°
# 4. At least 30 frames since last rep (debounce)
```

---

## Pipeline Modules

SAMARTH is architected around three decoupled processing modules (PS1, PS2, PS3). Each has a defined interface contract exposed through the backend service layer.

### PS1 - KinemaFlow (Computer Vision)

**Status: Integrated and active**

The PS1 pipeline (`/pipeline/`) is the team's existing computer vision engine. It is **never imported directly** by any backend route. All access goes through the `PoseEngineAdapter` singleton, which:

1. Injects the `/pipeline/` directory into `sys.path` at application startup
2. Exposes two operating modes:
   - **Real-time mode**: `process_frame(jpeg_bytes, frame_index, ts_ms, pose_estimator, kinematics)` → `RealtimeFrameResult`
   - **Batch mode**: `process_video(video_path, session_id, output_dir)` → `BatchProcessingResult`
3. Manages per-session `PoseEstimator` and `KinematicsExtractor` lifecycle (create/close)

**PS1 modules used:**
- `modules.pose_estimator.PoseEstimator` - MediaPipe Pose wrapper
- `modules.kinematics.KinematicsExtractor` - Joint angle computation from landmark coordinates
- `modules.background_seg.BackgroundSegmenter` - Background removal (batch mode)
- `modules.video_enhance.VideoEnhancer` - Brightness/contrast correction (batch mode)
- `modules.filter_utils` - Butterworth signal filtering
- `modules.feature_extractor` - Feature extraction utilities

### PS2 - Exercise Analysis ML Model

**Status: Integrated with RehabNet checkpoint**

The PS2 module analyses PS1 biomechanical time-series data to classify movement quality and detect error patterns. Set `PS2_MODEL_PATH=../pipeline/ps2/rehabnet_best.pth` and `PS2_USE_REAL_MODEL=true` in `.env` to load the real RehabNet analyzer. If the checkpoint cannot be loaded, the backend falls back to the mock analyzer instead of reporting fake real-model output.

**Error flags tracked (6 categories):**

| Flag | Description |
|---|---|
| `insufficient_ROM` | Knee flexion peak below target angle |
| `too_fast` | Rep duration below minimum threshold |
| `too_slow` | Rep duration above maximum threshold |
| `knee_valgus` | Inward knee collapse (medial deviation) |
| `asymmetric` | Left/right bilateral ROM difference > threshold |
| `trunk_comp` | Excessive trunk lateral flexion |

### PS3 - Wearable Sensor Hub

**Status: Stub (ready for integration)**

The PS3 module connects to BLE/IMU sensors (accelerometer, gyroscope) worn by the patient. A sensor HUD is rendered on the live session screen showing connection status and real-time inertial signals.

**To integrate your sensor firmware:**

1. Open [`backend/services/sensor_hub/`](backend/services/sensor_hub/)
2. Replace `mock_sensor.py` with BLE serial/bluetooth integration using `PS3_SENSOR_PORT` and `PS3_BAUD_RATE` from settings
3. Set `PS3_USE_REAL_SENSOR=true` in `.env`

---

## API Reference

All REST endpoints are prefixed with `/api/v1`. Full interactive documentation is available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register new user (patient or therapist) |
| `POST` | `/auth/login` | Login and receive access + refresh JWT tokens |
| `POST` | `/auth/refresh` | Refresh access token using refresh token |
| `GET` | `/auth/me` | Get authenticated user profile |
| `GET` | `/exercises/` | List all exercises in the library |
| `GET` | `/exercises/{id}` | Get single exercise details |
| `POST` | `/exercises/seed` | Seed default exercise library into database |
| `POST` | `/sessions/` | Create a new exercise session |
| `GET` | `/sessions/` | List sessions for authenticated patient |
| `GET` | `/sessions/{id}` | Get session details |
| `PUT` | `/sessions/{id}/complete` | Mark session as completed |
| `POST` | `/sessions/{id}/upload-video` | Upload recorded video for PS1 batch analysis |
| `GET` | `/sessions/{id}/angle-data` | Retrieve per-frame angle timeseries |
| `GET` | `/sessions/{id}/ps2-results` | Retrieve PS2 error analysis results |
| `GET` | `/analytics/patient/{id}/summary` | Patient-level aggregate analytics |
| `GET` | `/analytics/patient/{id}/weekly` | Week-by-week ROM and rep trends |
| `GET` | `/analytics/patient/{id}/rom-trends` | ROM trajectory over N days |
| `POST` | `/reports/generate` | Generate PDF/CSV clinical report |
| `GET` | `/reports/patient/{id}` | List generated reports for patient |
| `GET` | `/patients/` | List all patients (therapist-only) |
| `GET` | `/patients/{id}/sessions` | Get all sessions for a patient |
| `GET` | `/notifications/` | List notifications for current user |
| `PUT` | `/notifications/{id}/read` | Mark notification as read |
| `GET` | `/sensor/status` | PS3 sensor connection status |
| `GET` | `/health` | System health check |

---

## Repository Structure

```
dashboard/
│
├── pipeline/                        # PS1 KinemaFlow pipeline (DO NOT MODIFY)
│   ├── modules/
│   │   ├── pose_estimator.py        # MediaPipe Pose wrapper
│   │   ├── kinematics.py            # Joint angle extraction
│   │   ├── background_seg.py        # Background segmentation
│   │   ├── video_enhance.py         # Frame quality enhancement
│   │   └── filter_utils.py          # Signal filtering
│   └── main.py                      # run_pipeline_on_video() entry point
│
├── backend/
│   ├── main.py                      # FastAPI app, router registration, lifespan
│   ├── config.py                    # Pydantic settings (env-driven)
│   ├── database.py                  # Motor + Beanie initialisation
│   │
│   ├── api/                         # REST route handlers
│   │   ├── auth.py                  # Register / Login / Refresh / Me
│   │   ├── sessions.py              # Session CRUD + video upload
│   │   ├── exercises.py             # Exercise library + seed
│   │   ├── analytics.py             # Patient analytics queries
│   │   ├── patients.py              # Patient management (therapist view)
│   │   ├── reports.py               # PDF/CSV report generation
│   │   └── notifications.py         # Notification management
│   │
│   ├── ws_handlers/
│   │   ├── session_ws.py            # /ws/session/{id}/{token} - live exercise
│   │   └── camera_ws.py             # /ws/camera/{token} - camera validation
│   │
│   ├── models/                      # Beanie document models (14 collections)
│   │   ├── user.py                  # User (auth)
│   │   ├── patient.py               # Patient profile
│   │   ├── therapist.py             # Therapist profile
│   │   ├── session.py               # Exercise session
│   │   ├── angle_data.py            # Per-frame joint angles
│   │   ├── pose_data.py             # Raw landmark dump
│   │   └── ...                      # (analytics, report, notification, etc.)
│   │
│   └── services/
│       ├── auth_service.py          # JWT creation/verification, password hashing
│       ├── pose_engine/
│       │   ├── adapter.py           # PoseEngineAdapter - gateway to PS1
│       │   └── schemas.py           # RealtimeFrameResult, BatchProcessingResult, etc.
│       ├── exercise_analysis/       # PS2 ML stub - model_analyzer.py
│       └── sensor_hub/              # PS3 sensor stub - mock_sensor.py
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts            # Axios instance + JWT interceptor + auto-refresh
│   │   │   └── index.ts             # Typed API call functions
│   │   ├── components/
│   │   │   └── Layout.tsx           # Sidebar navigation + dark mode toggle
│   │   ├── pages/
│   │   │   ├── auth/                # Login + Register
│   │   │   ├── patient/
│   │   │   │   ├── PatientDashboard.tsx     # Session cards, quick stats
│   │   │   │   ├── ExerciseSelectionPage.tsx # Exercise library browser
│   │   │   │   ├── CameraValidationPage.tsx  # 10-check webcam validation
│   │   │   │   ├── LiveSessionPage.tsx       # Real-time angle gauges + rep counter
│   │   │   │   ├── UploadSessionPage.tsx     # Video upload + batch PS1
│   │   │   │   ├── SessionSummaryPage.tsx    # Post-session results
│   │   │   │   ├── AnalyticsPage.tsx         # ROM trends (Recharts)
│   │   │   │   └── ReportsPage.tsx           # PDF report generation
│   │   │   └── therapist/
│   │   │       ├── TherapistDashboard.tsx    # Patient roster + compliance
│   │   │       └── PatientDetailPage.tsx     # Per-patient ROM + session history
│   │   ├── stores/
│   │   │   └── authStore.ts         # Zustand store (tokens, user, logout)
│   │   ├── styles/
│   │   │   └── globals.css          # Design tokens, Tailwind components
│   │   └── types/                   # TypeScript interfaces
│   │
│   ├── vite.config.ts               # Vite + dev proxy (/api → :8000, /ws → :8000)
│   └── tailwind.config.ts           # Brand colours (#2A5BC4, #229096, #0F172A)
│
├── docker-compose.yml               # Backend + Frontend containers
├── .env                             # Root environment variables
└── logo.jpeg                        # SAMARTH brand mark
```


---

## Installation & Setup

### Prerequisites

| Requirement | Version |
|---|---|
| Node.js | 20 LTS or higher |
| Python | 3.10 or higher |
| MongoDB Atlas | Free tier (M0) or local MongoDB |

### Step 1 - Clone and configure environment

```bash
git clone <repository-url>
cd dashboard
cp .env.example .env
```

Edit `.env` and set at minimum:
```bash
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/<dbname>
JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_hex(64))">
```

### Step 2 - Backend setup

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file "../.env" --reload
```

> **Note:** If you encounter a `motor`/`pymongo` version conflict, run:
> ```bash
> pip install "motor==3.7.1" "beanie==1.26.0"
> ```

The Swagger API docs will be available at: **http://localhost:8000/docs**

### Step 3 - Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The application will be available at: **http://localhost:5173**

### Step 4 - Seed exercise library

On first run, seed the exercise database by calling:
```bash
curl -X POST http://localhost:8000/api/v1/exercises/seed
```

Or simply click **Start Exercise** on the patient dashboard - the UI auto-seeds on empty library.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGO_URI` | Yes | - | MongoDB Atlas connection string |
| `MONGO_DB_NAME` | No | `samarth` | MongoDB database name |
| `JWT_SECRET` | Yes | - | HS256 signing secret (min 64 chars) |
| `JWT_ALGORITHM` | No | `HS256` | Token signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `30` | Refresh token TTL |
| `FRONTEND_ORIGIN` | No | `http://localhost:5173` | CORS allowed origin |
| `STORAGE_BACKEND` | No | `local` | `local` or `cloudinary` |
| `LOCAL_UPLOAD_DIR` | No | `./uploads` | Local video upload directory |
| `CLOUDINARY_CLOUD_NAME` | No | - | Cloudinary cloud (production) |
| `CLOUDINARY_API_KEY` | No | - | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | No | - | Cloudinary API secret |
| `PS1_PIPELINE_PATH` | No | `../pipeline` | Relative path to PS1 directory |
| `PS1_STRIDE` | No | `2` | Frame stride for batch processing |
| `PS1_ENHANCE` | No | `true` | Enable video enhancement (batch) |
| `PS2_MODEL_PATH` | No | `../pipeline/ps2/rehabnet_best.pth` | Path to trained RehabNet PS2 model file |
| `PS2_USE_REAL_MODEL` | No | `true` | Enable real RehabNet inference when the model loads |
| `PS3_SENSOR_PORT` | No | `""` | Serial port for BLE sensor |
| `PS3_USE_REAL_SENSOR` | No | `false` | Enable real sensor reads |
| `PS3_BAUD_RATE` | No | `115200` | Serial baud rate |
| `WEASYPRINT_ENABLED` | No | `true` | Enable PDF report generation |
| `REPORTS_DIR` | No | `./reports` | Local directory for generated reports |

---

## Docker Deployment

A `docker-compose.yml` is provided for containerised deployment:

```bash
# From project root (dashboard/)
docker-compose up --build
```

This starts:
- **Backend** on port `8000` - FastAPI + Uvicorn, with `/pipeline/` mounted read-only
- **Frontend** on port `5173` - Vite dev server (or build for Nginx in production)

For production, set `STORAGE_BACKEND=cloudinary` and configure Cloudinary credentials to avoid relying on local filesystem for video storage.

---

## Integrating PS2 and PS3

### PS2 - RehabNet Exercise Analyzer

The system is wired to `backend/services/exercise_analysis/model_analyzer.py`, which loads `pipeline/ps2/rehabnet_best.pth`. Upload and live-session flows pass PS1 joint-angle data into RehabNet, then store the returned per-rep flags, confidence values, quality trend, score, and recommendations for the summary page.

1. Place your model weights file anywhere accessible to the backend
2. Set `PS2_MODEL_PATH=/absolute/path/to/model.pkl` in `.env`
3. Implement `analyze_rep()` in `backend/services/exercise_analysis/model_analyzer.py`:

```python
def analyze_rep(self, angle_timeseries: dict, rep_metadata: dict) -> dict:
    # angle_timeseries: {"left_knee": [float, ...], "right_knee": [...], ...}
    # rep_metadata: {"rep_index": int, "duration_ms": int, "target_rom": float}
    # Return:
    return {
        "quality_score": 0.85,        # 0.0 – 1.0
        "errors": {
            "insufficient_ROM": 0,     # count
            "too_fast": 0,
            "too_slow": 1,
            "knee_valgus": 0,
            "asymmetric": 0,
            "trunk_comp": 0,
        },
        "recommendations": ["Slow down your movement speed"]
    }
```

The `PS2_USE_REAL_MODEL` flag is **automatically set** to `true` when `PS2_MODEL_PATH` points to an existing file - no other config change needed.

### PS3 - Your Wearable Sensor

1. Implement your BLE/serial reader in `backend/services/sensor_hub/real_sensor.py`
2. The sensor HUD frontend component polls `GET /api/v1/sensor/status` and `GET /api/v1/sensor/data` at 2 Hz
3. Set `PS3_USE_REAL_SENSOR=true` and `PS3_SENSOR_PORT=/dev/ttyUSB0` (or `COM3` on Windows)

---

<div align="center">

**SAMARTH** - Physiotherapy · Machine Learning · Impact

*IIT (BHU) Varanasi*

</div>
