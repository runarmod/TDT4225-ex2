import mysql.connector as mysql


class DbConnector:
    """
    Connects to the MySQL server on the Ubuntu virtual machine.
    Connector needs HOST, DATABASE, USER and PASSWORD to connect,
    while PORT is optional and should be 3306.

    Example:
    HOST = "tdt4225-01.idi.ntnu.no" // Your server IP address/domain name
    DATABASE = "test_db" // Database name, if you just want to connect to MySQL server, leave it empty
    USER = "mysql_user" // This is the user you created and added privileges for
    PASSWORD = "mysql_password" // The password you set for said user
    """

    def __init__(
        self,
        HOST="tdt4225-01.idi.ntnu.no",
        DATABASE="test_db",
        USER="mysql_user",
        PASSWORD="mysql_password",
    ):
        # Connect to the database
        try:
            self.db_connection = mysql.connect(
                host=HOST, database=DATABASE, user=USER, password=PASSWORD, port=3306
            )
        except Exception as e:  # noqa: BLE001
            print("ERROR: Failed to connect to db:", e)

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


if __name__ == "__main__":
    db_connector = DbConnector(
        HOST="localhost",
        DATABASE="porto_db",
        USER="mysql_user",
        PASSWORD="mysql_password",
    )
    db_connector.close_connection()
