import os
from datetime import date, datetime
from decimal import Decimal

from dotenv import load_dotenv
from hdbcli import dbapi

load_dotenv(override=True)


def get_hana_connection():
    return dbapi.connect(
        address=os.environ["HANA_HOST"],
        port=int(os.environ.get("HANA_PORT")),
        user=os.environ["HANA_USER"],
        password=os.environ["HANA_PASSWORD"],
        encrypt="true",
        sslValidateCertificate="true"
    )


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    return value


def execute_query(sql, parameters=()):
    connection = None
    cursor = None

    try:
        connection = get_hana_connection()
        cursor = connection.cursor()
        cursor.execute(sql, parameters)

        column_names = [column[0].lower() for column in cursor.description]
        rows = cursor.fetchall()

        return [
            {
                column_names[index]: serialize_value(value)
                for index, value in enumerate(row)
            }
            for row in rows
        ]

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()
