🚀 FastAPI Finance & Installment Tracker
A robust, reactive financial dashboard built to track credit card installments, monthly "burn" rates, and future payment forecasts. This project focuses on high-performance server-side rendering and complex relational data modeling.

🎯 Key Features
[x] Live Dashboard: Real-time "Monthly Burn" and "Remaining Debt" calculation using HTMX Out-of-Bounds (OOB) swaps.

[x] Forecast Engine: Dynamic monthly views to predict future bill payments based on active installments.

[x] Eager Loading: Optimized database queries using SQLAlchemy joinedload to prevent "Lazy Load" errors and improve performance.

[x] Reactive UI: Modern, pill-style summary cards and progress bars built with Tailwind CSS.

[x] Modular Backend: Professional Python package structure separating models, logic, and route handling.

🛠️ Tech Stack
Framework: FastAPI (Python 3.13)

Database/ORM: SQLAlchemy (SQLite) with relational mapping

Frontend: HTMX (for SPA interactivity), Tailwind CSS (for styling), Jinja2 (templating)

Utilities: python-dateutil for complex recurring date math

🚦 Quick Start
Install Dependencies: pip install fastapi uvicorn sqlalchemy bcrypt python-multipart python-dateutil

Launch Server: uvicorn main:app --reload

Access Dashboard: Navigate to http://127.0.0.1:8000
