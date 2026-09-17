import os

import mysql.connector as mysql
from dotenv import load_dotenv

load_dotenv()


class DbConnector:
    """
    Connects to the MySQL server on the Ubuntu virtual machine.
    Connector needs HOST, DATABASE, USER and PASSWORD to connect,
    while PORT is optional and should be 3306.

    Connection settings are read from environment variables, which can be
    set in a .env file (see .env.example).

    Example .env:
    DB_HOST=tdt4225-01.idi.ntnu.no // Your server IP address/domain name
    DB_DATABASE=test_db // Database name, if you just want to connect to MySQL server, leave it empty
    DB_USER=mysql_user // This is the user you created and added privileges for
    DB_PASSWORD=mysql_password // The password you set for said user
    """

    def __init__(
        self,
        HOST=None,
        DATABASE=None,
        USER=None,
        PASSWORD=None,
        PORT=None,
    ):
        HOST = default_if_none(HOST, os.getenv("DB_HOST", "tdt4225-01.idi.ntnu.no"))
        DATABASE = default_if_none(DATABASE, os.getenv("DB_DATABASE"))
        USER = default_if_none(USER, os.getenv("DB_USER"))
        PASSWORD = default_if_none(PASSWORD, os.getenv("DB_PASSWORD"))
        PORT = default_if_none(PORT, os.getenv("DB_PORT", "3306"))

        # Connect to the database
        try:
            self.db_connection = mysql.connect(
                host=HOST,
                database=DATABASE,
                user=USER,
                password=PASSWORD,
                port=int(PORT),
            )
        except Exception as e:
            print("ERROR: Failed to connect to db:", e)
            raise

        # Get the db cursor
        self.cursor = self.db_connection.cursor()

        print("Connected to:", self.db_connection.get_server_info())
        # get database information
        self.cursor.execute("select database();")
        database_name = self.cursor.fetchone()
        print("You are connected to the database:", database_name)
        print("-----------------------------------------------\n")

    def close_connection(self):
        # close the cursor
        self.cursor.close()
        # close the DB connection
        self.db_connection.close()
        print("\n-----------------------------------------------")
        print(f"Connection to {self.db_connection.get_server_info()} is closed")


def default_if_none(value, default):
    return value if value is not None else default


if __name__ == "__main__":
    db_connector = DbConnector()
    db_connector.close_connection()
