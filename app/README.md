# Disaster Relief Drone System Backend

This is the backend API service for the disaster relief drone system built with FastAPI and PostgreSQL.

## Prerequisites

- Docker and Docker Compose
- Python 3.9+
- PostgreSQL (if running locally)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Create a virtual environment (optional, for local development):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Environment Configuration:
   - Copy `.env.example` to `.env`
   - Update the environment variables with your actual values:
     - `DATABASE_URL`: PostgreSQL connection string
     - `SUPABASE_URL`: Your Supabase project URL
     - `SUPABASE_KEY`: Your Supabase project key

## Running the Application

### Using Docker Compose (recommended)

1. Build and start the services:
```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`

### Running Locally

1. Make sure PostgreSQL is running and accessible
2. Start the FastAPI server:
```bash
cd app
uvicorn main:app --reload
```

## API Documentation

Once the server is running, you can access:
- Interactive API documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative API documentation (ReDoc): `http://localhost:8000/redoc`

## Development

- The application structure follows standard FastAPI practices
- Models are defined in `/app/models`
- API routes are in `/app/routers`
- Pydantic schemas are in `/app/schemas`
- Database configuration is in `/app/db.py`

## Testing

To run tests (once implemented):
```bash
pytest
```