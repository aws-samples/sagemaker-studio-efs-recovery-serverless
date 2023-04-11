import boto3
import argparse
from common import users as u
from common import users_history as hist
import time
import sys
from botocore.exceptions import ClientError

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-src-domain-name",
        "--src-domain-name",
        dest="src_domain_name",
        type=str
    )
    parser.add_argument(
        "-target-domain-name",
        "--target-domain-name",
        dest="target_domain_name",
        type=str
    )
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str
    )
    parser.add_argument(
        "-src-profile-name",
        "--src-profile-name",
        dest="src_profile_name",
        type=str
    )
    parser.add_argument(
        "-target-profile-name",
        "--target-profile-name",
        dest="target_profile_name",
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
    args = parser.parse_args()
    table = args.table_name
    history_table = args.history_table_name
    src_profile_name = args.src_profile_name
    src_domain_name = args.src_domain_name
    target_profile_name = args.target_profile_name
    target_domain_name = args.target_domain_name
    region = args.region
    table_key = {"domain_name": src_domain_name, "profile_name": src_profile_name}
    target_table_key = {"domain_name": target_domain_name, "profile_name": target_profile_name}
    print(f"Read table {table} with key {table_key}")
    ddb_resource = boto3.resource('dynamodb', region)
    users = u.Users(ddb_resource, args.table_name)
    print("table exists")
    print('-' * 50)
    item = users.get_user(key=table_key)
    print(f"get user(source) with key {table_key} returned item: {item}")
    print('-' * 50)
    item_target = users.get_user(key=target_table_key)
    print(f"get user(target) with key {target_table_key} returned item: {item_target}")
    if item_target:
        sys.exit(f"target domain_name {target_domain_name}, target profile_name {target_profile_name} already exists. Try different profile.")
    ## target doesn't exist yet. replication takes place on subsequent create profile event.
    print('-' * 50)
    print(f"append table {table} with new domain {target_domain_name} and profile names {target_profile_name}")
    item['profile_name'] = target_profile_name
    item['domain_name'] = target_domain_name
    item['replication'] = True
    response = users.update_user(
        key=target_table_key,
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
            "profile_name": target_profile_name,
            "epoctime": int(time.time() * 1000),
            "replication": item['replication'],
            "role_name": item['role_name'],
            "domain_id": item['domain_id'],
            "domain_name": target_domain_name,
            "user_profile_name": item['user_profile_name'],
            "space_name": item['space_name'],
            "efs_sys_id": item['efs_sys_id'],
            "efs_uid": item['efs_uid']
        }
    )
print("Done")


