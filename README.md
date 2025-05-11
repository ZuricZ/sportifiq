# Tennis Court Booking Automation

This repository contains a GitHub Actions workflow that automates tennis court bookings. The current workflows are:
- runs every Sunday at 1:00 AM UTC (Sunday at 18h)
- runs every Saturday at 1:00 AM UTC (Saturday at 10h)
- runs every Wednesday at 1:00 AM UTC (Wednesday at 18h)


## Workflow Configuration

The workflow is defined in `.github/workflows` folder. To create your own workflow you need to create a new `yml` file and use the structure of previous ones. You need to modify following parameters:

### 1. Schedule Configuration
```yaml
schedule:
  - cron: "0 1 * * 0"
```
- Modify the cron expression to change when the workflow runs
- Format: `"minute hour day-of-month month day-of-week"`
- Current setting: Runs at 1:00 AM every Sunday
- [Cron Expression Generator](https://crontab.generator.expert/)

### 2. Environment Variables
The following environment variables can be modified in the workflow:

```yaml
env:
    USER_PASS: ${{ secrets.PASS_1}}    # Your booking password
    USER_EMAIL: ${{ secrets.USER_1 }}  # Your email
    DAY: "Ned"                         # Day of the week (e.g., "Ned" for Sunday)
    HOUR: "18:00"                      # Booking time
    NUM_SESSIONS: 2                    # Number of sessions to book
    VENUE: "Tivoli"                    # Venue name
    COURT_NAME: "Igrišče 1"            # Primary court
    BACKUP_COURT_NAME: "Igrišče 2"     # Backup court
```

### 3. Setting up Secrets
1. Go to your GitHub repository
2. Navigate to Settings > Secrets and variables > Actions
3. Add the following secrets:
   - `PASS_1`: Your booking password
   - `USER_1`: Your email address

## Troubleshooting and local runing

- Make sure your `requirements.txt` includes all necessary Python packages
- In file config.json set `debug_mode: True` in order to use localy store parameters. Please make sure that debug_mode is set to False after that.