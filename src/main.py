import argparse
import json
import sys

from libs.reserve_session import configure_driver, get_venue_to_url_map, login_to_website, choose_day, \
    manage_primary_and_backup_bookings
from libs.utils import decrypt_password, str2bool


def get_arguments():
    """
    Return the arguments parsed from command line and config file.

    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Book court for given day and time.")
    parser.add_argument("--day", required=True,
                        choices=["Pon", "Tor", "Sre", "Čet", "Pet", "Sob", "Ned",
                                 "Ponedeljek", "Torek", "Sreda", "Četrtek", "Petek", "Sobota", "Nedelja"],
                        help="Target Day. Be sure to check the name of the day on the website. "
                             "First two days seem to be fully spelled out")
    parser.add_argument("--hour", required=True, type=str,
                        help="Target Hour in '%H:%M' format")
    parser.add_argument("--num_sessions", type=int, required=True,
                        help="Number of *hourly* sessions to book")
    parser.add_argument("--venue", required=True,
                        choices=['tivoli', 'svoboda', 'koseze'], type=str.lower,
                        help="Venue of booking")
    parser.add_argument("--court_name", required=True, type=str,
                        help="Exact name of the court to reserve")
    parser.add_argument("--backup_court_name", type=str,
                        help="Backup court name")
    parser.add_argument("--user_email", required=True, type=str,
                        help=" User Email")
    parser.add_argument("--debug_mode", type=str2bool, default=False, help="Debug mode")

    # Read arguments from json file
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    argv = [[f'--{k}', str(v)] for k, v in config.items()]
    argv = sum(argv, [])
    args = parser.parse_args(argv)
    return args

def serve_args():
    '''Parse input arguments'''
    parser = argparse.ArgumentParser("train")
    parser.add_argument("--serve", type=str, help="Path to first serve")

    args = parser.parse_args()
    with open(args.serve, "rb") as f:
        serve_= json.load(f)
    return serve_

def main():
    """
    Main Method

    This method is the entry point to the program. It performs the following steps:
    1. Retrieves command line arguments using the `get_arguments()` function.
    2. Retrieves a mapping of venue names to their corresponding URLs using the `get_venue_to_url_map()` function.
    3. Retrieves the URL for the specified venue from the mapping.
    4. Decrypts the password using the `decrypt_password()` function.
    5. Configures the web driver with the specified options, such as headless mode, using the `configure_driver()` function.
    6. Logs in to the website using the `login_to_website()` function, providing the driver, venue URL, user email, and decrypted password as arguments.
    7. Chooses the specified day using the `choose_day()` function, providing the driver and day as arguments.
    8. Manages the primary and backup bookings using the `manage_primary_and_backup_bookings()` function, providing the driver and command line arguments as arguments.

    :return: None
    """
    args = get_arguments()

    print("Here 1")
    venue_url_map = get_venue_to_url_map()
    venue_url = venue_url_map[args.venue]
    #password = decrypt_password()
    #password = serve_args().get('first-serve')
    import os
    try:
        password = os.environ["PASS"]
    except KeyError:
        password = "Pass not available!"
    # or raise an error if it's not available so that the workflow fails
    print("Tukaj 2")
    driver = configure_driver(headless_mode=not args.debug_mode)
    print("Tukaj 3")
    login_to_website(driver, venue_url, args.user_email, password)
    print("Tukaj 4")
    choose_day(driver, args.day)
    # book sessions for primary court, and rebook unsuccessful bookings on backup court
    manage_primary_and_backup_bookings(driver, args)


if __name__ == '__main__':
    main()
    print('Booked successfully!')
