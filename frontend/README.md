# Guideon Chatbot

A web application built with React+Vite frontend and Django backend.

## Setup

### Backend Setup
1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install the required Node packages:
   ```
   npm install
   ```

## Quick Start

To start both frontend and backend servers with a single command:

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Run the start command:
   ```
   npm run start
   ```

This will automatically start both the Django backend server and the Vite development server for the frontend.

## Technology Stack

- **Frontend**: React, Vite, TailwindCSS
- **Backend**: Django REST Framework

## Development

For individual development:

- **Frontend only**: `npm run start-frontend` or `npm run dev`
- **Backend only**: `npm run start-backend` or `cd ../backend && python manage.py runserver`

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh
