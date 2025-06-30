# 🩸 Blood Bank Management System

A full-stack web application built using **Flask** and **MySQL**, designed to manage and track blood donors, recipients, blood stock, and donation requests. The system features a secure login, registration, dashboard, and real-time data management for hospital or blood bank use.


---

## 🚀 Features

- 👤 **User Authentication**
  - Login & Registration (auth module)
- 🩸 **Donor & Recipient Management**
  - Add/view donor and recipient details
- 📊 **Blood Stock Monitoring**
  - Track and manage available blood types
- 🔄 **Transactions**
  - Request and fulfill blood donation needs
- 📋 **Dashboard**
  - Clean UI with navigation and analytics
- 📦 **Modular Structure**
  - Organized templates and components

---

## 💻 Technologies Used

| Stack        | Tools                      |
|--------------|----------------------------|
| **Frontend** | HTML, CSS, Bootstrap       |
| **Backend**  | Python, Flask              |
| **Database** | MySQL                      |
| **Others**   | Jinja2, dotenv, Flask-WTF  |

---


## 🗂️ Project Structure

Blood Bank System/
│
├── static/ # Static assets
│ ├── css/ # Stylesheets
│ └── js/ # JavaScript files
│
├── templates/ # HTML templates
│ ├── auth/ # Login/Register pages
│ ├── blood/ # Blood stock pages
│ ├── components/ # Reusable components (navbar, footer, etc.)
│ ├── donor/ # Donor-related pages
│ ├── recipient/ # Recipient-related pages
│ ├── transaction/ # Request/transaction management
│ ├── base.html # Base layout file
│ └── dashboard.html # Main dashboard
│
├── app.py # Main Flask app
├── config.py # App and database config
├── requirements.txt # Python dependencies
├── wsgi.py # For production deployment
├── .env # Environment variables (DB credentials etc.)
└── venv/ # Virtual environment
