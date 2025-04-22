# Guideon Chatbot

A web application built with React+Vite frontend and Django backend.

## Getting Started

### Clone the Repository
```bash
git clone https://github.com/yourusername/guideon-chatbot.git
cd guideon-chatbot
```

## Setup

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # macOS/Linux
   python -m venv venv
   source venv/Scripts/activate
   ```

3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Apply migrations:
   ```bash
   python manage.py migrate
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install the required Node packages:
   ```bash
   npm install
   ```

## Quick Start

To start both frontend and backend servers with a single command:

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Run the start command:
   ```bash
   npm run start
   ```

This will automatically start both the Django backend server and the Vite development server for the frontend.

## Technology Stack

- **Frontend**: React, Vite, TailwindCSS
- **Backend**: Django REST Framework
- **Database**: PostgreSQL

## Development

For individual development:

- **Frontend only**: `npm run start-frontend` or `npm run dev`
- **Backend only**: `npm run start-backend` or `cd ../backend && python manage.py runserver`

## Project Structure
```
guideon-chatbot/
├── backend/          # Django backend
│   ├── api/          # REST API endpoints
│   └── ...
└── frontend/         # React+Vite frontend
    ├── src/          # Application source code
    │   ├── components/  # Reusable UI components
    │   ├── pages/    # Application views/routes
    │   ├── services/ # API service integrations
    │   └── types/    # TypeScript type definitions
    └── ...
```

## Environment Setup

For production deployment, you might want to configure environment variables:

1. Create a `.env` file in the backend directory for Django settings
2. Create a `.env` file in the frontend directory for React/Vite settings

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh
