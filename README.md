# Sportifiq
Sportifiq is a Python application used for booking court sessions and developed in PyCharm 2024.1, Professional Edition on Python 3.11.8.
# Project Description
This program automates the process of court reservation for certain specified days, hours, and venues. It is designed to book a specific number of hourly sessions and to handle primary and backup bookings.
# Installation
You can install these packages using pip or conda:
```
pip install -r requirements.txt
```
This command should be run in the project directory where requirements.txt is located.
# Usage
The program can be used with a variety of command-line arguments to specify the details of the reservation.
* `--day`: Specify the target day (e.g., "Mon", "Tue", etc.)
* `--hour`: Specify the target hour in '%H:%M' format
* `--num_sessions`: Specify the number of hourly sessions to book
* `--venue`: Specify the venue of booking (e.g., "tivoli", "svoboda", "koseze")
* `--court_name`: Specify the exact name of the court to reserve
* `--backup_court_name`: Specify the backup court name
* `--user_email`: Specify the user email
* `--debug_mode`: Enable or disable debug mode
