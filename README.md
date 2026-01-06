# 💳 Credit Card Installment Tracker

A secure, modular web application designed to track and manage monthly credit card installments. This project helps users monitor their total monthly "burn," debt distribution across different cards, and payment timelines.

## 🚀 Features
- **Secure Authentication**: User login powered by `bcrypt` password hashing.
- **Relational Database**: Tracks Users, Credit Cards, Owners, and Installments using SQLAlchemy.
- **Dynamic UI**: Interactive forms and real-time updates using **HTMX** and **Tailwind CSS**.
- **Modular Architecture**: Clean separation of concerns (Models, Database, Seeds, and Routes).

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python 3.13+)
- **Database**: SQLite & SQLAlchemy
- **Frontend**: HTMX, Jinja2 Templates, Tailwind CSS
- **Security**: Bcrypt

## 📦 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone [https://github.com/leirajyer/installment-tracker.git](https://github.com/leirajyer/installment-tracker.git)
   cd installment-tracker
