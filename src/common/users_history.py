import string
import boto3
from typing import Mapping
from botocore.exceptions import ClientError
import logging
import argparse

logger = logging.getLogger(__name__)
logger.setLevel('ERROR')

class UsersHistory:
    def __init__(self, ddb_resource, table_name):
        self.ddb_resource = ddb_resource
        self.table = None
        try:
            table = self.ddb_resource.Table(table_name)
            table.load()
            self.table = table
        except ClientError as e:
            logger.error(
                f"Table {table_name} not found: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
            raise

    def put_user(self, item: Mapping) -> Mapping:
        try:
            response = self.table.put_item(
                Item=item
            )
        except ClientError as e:
            logger.error(
                f"Could not appen an item to table: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
            raise
        return response

    def get_user(self, key: Mapping) -> Mapping:
        try:
            response = self.table.get_item(
                Key=key
            )
        except ClientError as e:
            logger.error(
                f"Could not get user: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
            raise
        if 'Item' in response:
            return response['Item']
        return {}

    def query(self, attribute: string) -> Mapping:
        try:
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user').eq(attribute)
            )
        except ClientError as e:
            logger.error(
                f"Could not get user: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
            raise
        return response['Items']

def run_question(ddb_resource, table_name, attribute):
    print('-' * 50)
    users = UsersHistory(ddb_resource, table_name)
    print("table exists")
    print('-' * 50)
    item = users.query(attribute=attribute)
    print(f"get records with attribute {attribute} returned {len(item)} items: {item}")
    print('-' * 50)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str,
        description="aws region name"
    )
    parser.add_argument(
        "-table-name",
        "--table-name",
        dest="table_name",
        type=str,
        description="studio user history table name",
        default='studioUserHisotry'
    )
    parser.add_argument(
        "-attribute",
        "--attribute",
        dest="attribute",
        type=str,
        default='user1'
    )
    args = parser.parse_args()
    run_question(
        ddb_resource=boto3.resource('dynamodb', args.region),
        table_name=args.table_name,
        attribute=args.attribute
    )
