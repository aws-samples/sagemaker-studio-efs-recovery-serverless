import json
import string
import boto3
from typing import Mapping
from botocore.exceptions import ClientError, ParamValidationError
import logging
import argparse

logger = logging.getLogger(__name__)
logger.setLevel('ERROR')

class Users:
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

    def update_user(self, key: Mapping, expression: string, attributes: Mapping,ret_val: string) -> Mapping:
        try:
            response = self.table.update_item(
                Key=key,
                UpdateExpression=expression,
                ExpressionAttributeValues=attributes,
                ReturnValues=ret_val
            )
        except ParamValidationError as e:
            logger.error(
                f"Could not update table because wrong parameters provided: key={key}, expression={expression}, attributes={attributes}")
            raise
        except ClientError as e:
            logger.error(
                f"Could not update table: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
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
        return response['Item']

def run_question(ddb_resource, table_name, key):
    print('-' * 50)
    users = Users(ddb_resource, table_name)
    print("table exists")
    print('-' * 50)
    item = users.get_user(key=key)
    print(f"get user with key {key} returned item: {item}")
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
        description="studio user table name",
        default='studioUser'
    )
    parser.add_argument(
        "-key",
        "--key",
        dest="key",
        type=str,
        description='{"user": <studio user profile name>, "role_name": <sagemaker notebook execution role name>}'
    )
    args = parser.parse_args()
    run_question(
        ddb_resource=boto3.resource('dynamodb', args.region),
        table_name=args.table_name,
        key=json.loads(args.key)
    )
