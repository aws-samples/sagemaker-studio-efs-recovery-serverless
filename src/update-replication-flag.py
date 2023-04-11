import json
import boto3
import argparse
import os
from common import users as u
from common import users_history as hist
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-domain-name",
        "--domain-name",
        dest="domain_name",
        type=str
    )
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str
    )
    parser.add_argument(
        "-profile-name",
        "--profile-name",
        dest="profile_name",
        type=str
    )
    parser.add_argument(
        "-table-name",
        "--table-name",
        dest="table_name",
        type=str,
        default='studioUser'
    )
    parser.add_argument(
        "-history-table-name",
        "--history-table-name",
        dest="history_table_name",
        type=str,
        default='studioUserHistory'
    )
    parser.add_argument(
        "-replication",
        "--replication",
        dest="replication",
        action='store_true'
    )
    parser.add_argument(
        "-no-replication",
        "--no-replication",
        dest="replication",
        action='store_false'
    )
    parser.set_defaults(replication=True)
    args = parser.parse_args()
    table = args.table_name
    history_table = args.history_table_name
    profile_name = args.profile_name
    domain_name = args.domain_name
    region = args.region
    replication = args.replication
    table_key = {"domain_name": domain_name, "profile_name": profile_name}

    print(f"Read table {table} with key {table_key}")
    ddb_resource = boto3.resource('dynamodb', region)
    users = u.Users(ddb_resource, args.table_name)
    print("table exists")
    print('-' * 50)
    item = users.get_user(key=table_key)
    print(f"get user with key {table_key} returned item: {item}")
    print('-' * 50)
    print(f"update table {table} and set replication flag")
    item['replication'] = replication
    response = users.update_user(
        key=table_key,
        expression="set replication = :rp, domain_id = :d, user_profile_name = :upn, space_name = :s, efs_sys_id =:es, efs_uid = :eu, role_name =:rn",
        attributes={
            ":rp": item['replication'],
            ":rn": item['role_name'],
            ":d": item['domain_id'],
            ":upn": item['user_profile_name'],
            ":s": item['space_name'],
            ":es": item['efs_sys_id'],
            ":eu": item['efs_uid']
        },
        ret_val='ALL_NEW'
    )
    print(f"update table {table} respose: {response}")
    print('-' * 50)
    users_hist = hist.UsersHistory(
        ddb_resource=ddb_resource,
        table_name=history_table
    )
    print(f"append the item into table {history_table}")
    users_hist.put_user(
        item={
            "profile_name": profile_name,
            "epoctime": int(time.time() * 1000),
            "replication": item['replication'],
            "role_name": item['role_name'],
            "domain_id": item['domain_id'],
            "domain_name": domain_name,
            "user_profile_name": item['user_profile_name'],
            "space_name": item['space_name'],
            "efs_sys_id": item['efs_sys_id'],
            "efs_uid": item['efs_uid']
        }
    )
    print("Done")


