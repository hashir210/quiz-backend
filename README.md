# 🚀 Quiz App Backend

A high-performance, real-time backend API built to power an interactive, live-action quiz platform. Engineered with modern asynchronous Python, this API handles everything from secure teacher authentication to sub-second real-time websocket broadcasting for live quiz sessions.

## 🛠️ Tech Stack

- **Core Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Async Python)
- **Database:** PostgreSQL hosted on [Supabase](https://supabase.com/)
- **ORM & Migrations:** SQLAlchemy (Asyncpg) + Alembic
- **Real-time Engine:** Native WebSockets (Custom In-Memory Connection Manager)
- **Authentication:** JWT (JSON Web Tokens) with Passlib (Bcrypt) hashing
- **Object Storage:** Supabase Storage (for quiz images)

## ✨ Key Features

- **Real-time Gameplay:** Custom WebSocket connection manager handling live rooms, instant broadcasting, and student lifecycle events.
- **Dynamic Scoring Engine:** Server-side score calculations based on response speed to entirely eliminate client-side cheating.
- **Teacher Dashboard API:** Full CRUD endpoints for managing quizzes, questions, and generating instant room codes.
- **Media Support:** Built-in upload endpoints that securely push images to Supabase Storage.
- **QR Code Generation:** Dynamic QR codes generated on the fly for seamless mobile student onboarding.

## 🚀 Local Development Setup

### 1. Prerequisites
- Python 3.10+
- PostgreSQL Database (or a free Supabase project)

### 2. Installation

Clone the repository and set up a virtual environment:

```bash
git clone git@github.com:hashir210/quiz-backend.git
cd quiz-backend
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root directory based on `.env.example`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
SUPABASE_URL=https://[YOUR_REF].supabase.co
SUPABASE_KEY=your_service_role_key
SECRET_KEY=generate_a_random_secure_string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=7
FRONTEND_URL=http://localhost:5173
ENVIRONMENT=development
```

### 4. Database Migrations

Run Alembic to create all necessary database tables:

```bash
alembic upgrade head
```

### 5. Running the Server

Start the local development server:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. 
Interactive API documentation (Swagger) can be found at `http://localhost:8000/docs`.

## 📦 Deployment

This backend is configured perfectly for deployment on platforms like **Railway** or **Render**. 
Simply connect the GitHub repository, inject your `.env` variables, and ensure `ENVIRONMENT=production` to secure the API documentation endpoints.
