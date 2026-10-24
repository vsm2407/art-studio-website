# Art Studio Website 🎨

A full-stack Art Studio website where customers can explore and purchase unique paintings, book wall-painting services, and request custom pottery.

## Features

### Customer Features
- Create an account and log in securely.
- Browse paintings and purchase available artworks.
- Cancel eligible painting orders.
- Book wall-painting services by selecting a date, area, and address.
- Calculate wall-painting costs based on the selected area.
- Submit custom pottery requests with item, glaze, quantity, and required date.
- View and manage eligible bookings and requests.

### Admin Features
- Manage painting availability and artwork details.
- View and manage wall-painting bookings.
- Confirm or decline wall-painting bookings.
- Review and manage custom pottery requests.
- Accept or decline pottery requests.

## Technology Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python, Flask
- **Database:** MySQL
- **Authentication:** Flask sessions and password hashing
- **Database Connector:** mysql-connector-python

## Project Structure

```text
art-studio-website/
├── app.py
├── database/
├── seedData/
├── static/
├── templates/
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── DESIGN.md
```

## Prerequisites

Install the following before running the project:

- Python 3
- MySQL Server
- Git (optional, for cloning the repository)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/vsm2407/art-studio-website.git
cd art-studio-website
```

Alternatively, download the repository as a ZIP file and extract it.

### 2. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create your local `.env` file by copying the example:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

Edit `.env` and provide your own Flask secret key and MySQL connection settings.

Never commit your `.env` file or real credentials to GitHub.

### 4. Set Up MySQL

- Start your MySQL server.
- Create the database configured in your `.env` file.
- Use the SQL files in the `database/` directory to initialize the database.
- Follow the project's seed-data files and setup instructions to populate the initial paintings, pottery options, glazes, and administrator account.

Use the actual SQL filenames and instructions present in the repository. Do not import the schema over an existing database containing data unless you understand the effects.

### 5. Run the Application

```bash
python app.py
```

Open the local address displayed in the terminal, usually:

http://127.0.0.1:5000/

## Security

- Passwords are hashed rather than stored as plain text.
- Session-based authentication is used.
- Customer and administrator access is restricted by role.
- Environment variables are used for secret configuration.
- The `.env` file is excluded from version control.

## Project Scope

This project demonstrates a database-backed art studio service platform with painting purchases, wall-painting bookings, custom pottery requests, and administrative workflows.

Online payment processing, email verification, password recovery, and deployment infrastructure are outside the current project scope.

## Future Improvements

- Add online payment integration.
- Improve image browsing and artwork filtering.
- Add booking notifications.
- Deploy the application to a production hosting platform.

## Author

Developed as a web development project using Flask, MySQL, HTML, CSS, and JavaScript.
