# Django React Full Stack App – Setup Guide

---

## **Backend (Django) Setup:**

1. **Clone the Repository:**
   - Run the command:  
     `git clone https://github.com/lalalance12/guideon-chatbot.git`  
     Then navigate into the project folder.

2. **Create and Activate a Virtual Environment:**
   - **To create a virtual environment:**  
     `python -m venv venv`
   - **To activate it:**
     - On **Windows:** `venv\Scripts\activate`
     - On **macOS/Linux:** `source venv/bin/activate`

3. **Install the Required Python Packages:**
   - Run:  
     `pip install -r requirements.txt`

4. **Configure Environment Variables:**
   - Create a file named **.env** in the backend directory with the following lines:
     ```
     DB_NAME=""
     DB_USER=""
     DB_PASSWORD=""
     DB_HOST=""
     DB_PORT=""
     ```
     *(Fill in the actual database credentials as needed.)*

5. **Run Database Migrations:**
   - Execute:  
     `python manage.py migrate`

6. **Start the Django Development Server:**
   - Execute:  
     `python manage.py runserver`  
     The backend should now be running at **http://localhost:8000**

---

## **Frontend (React) Setup:**

1. **Navigate to the Frontend Directory:**
   - Run:  
     `cd frontend`

2. **Install the Node.js Dependencies:**
   - Run:  
     `npm install`  
     *(Alternatively, use `yarn install` if preferred.)*

3. **Configure Environment Variables:**
   - Create a file named **.env** in the frontend directory with the following line:
     ```
     VITE_API_URL=http://localhost:8000
     ```

4. **Start the React Development Server:**
   - Execute:  
     `npm run dev` 
     The React application should now be running at **http://localhost:3000**

---

> **Note:** Ensure that the Django server (backend) is running while you develop and test the React app.

