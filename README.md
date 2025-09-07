Campus Event Reporting System

This project is a simple event management and reporting prototype built for the Webknot Campus Drive assignment. It allows colleges to create events, students to register, and admins to track attendance and feedback. Reports can then be generated to see event popularity and student participation.

My Understanding

The system mainly covers:

Event creation

Student registration

Attendance marking

Collecting feedback

Generating reports (event popularity, participation, top students)

Tech Stack

Flask (Python) – for APIs

SQLite – for database

SQL Queries – for reports

How to Run

Install dependencies: pip install flask

Initialize database: python seed.py

Run server: python app.py

Access reports in browser/Postman, e.g. http://127.0.0.1:5000/reports/event-popularity

Limitations / Next Steps

No authentication added yet

UI not included (only backend + APIs)

Currently SQLite, can be migrated to MySQL/Postgres

Future scope: filters, dashboards, student app UI
