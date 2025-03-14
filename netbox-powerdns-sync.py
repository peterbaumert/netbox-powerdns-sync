#!/usr/bin/env python3

import powerdns
import pynetbox
import re
import ipaddress
import os

from config import NB_URL, NB_TOKEN, PDNS_API_URL, PDNS_KEY
from config import REQUESTS_CA_BUNDLE
from config import DEBUG

os.environ["REQUESTS_CA_BUNDLE"] = REQUESTS_CA_BUNDLE
nb = pynetbox.api(NB_URL, token=NB_TOKEN)

pdns_api_client = powerdns.PDNSApiClient(api_endpoint=PDNS_API_URL, api_key=PDNS_KEY)
pdns = powerdns.PDNSEndpoint(pdns_api_client).servers[0]

FORWARD_ZONES = nb.plugins.netbox_dns.zones.filter(tag=["forward-zone"])
REVERSE_ZONES = nb.plugins.netbox_dns.zones.filter(tag=["reverse-zone"])

host_ips = []
record_ips = []
record_wo_comment_ips = []
for forward_zone in FORWARD_ZONES:
    forward_zone_canonical = forward_zone.name + "."

    # get IPs with DNS name ending in forward_zone from NetBox
    records = nb.plugins.netbox_dns.records.filter(
        zone=forward_zone.name, type__n=["NS", "SOA"]
    )

    # assemble list with tupels containing the canonical name, the record type
    # and the IP address without the subnet from NetBox IPs
    for record in records:
        host_ips.append(
            (
                record.name + "." + forward_zone_canonical,
                record.type,
                record.value,
                forward_zone_canonical,
            )
        )

    # get zone forward_zone_canonical form PowerDNS
    zone = pdns.get_zone(forward_zone_canonical)

    # assemble list with tupels containing the canonical name, the record type,
    # the IP address and forward_zone_canonical without the subnet from
    # PowerDNS zone records with the
    # comment "NetBox"
    for record in zone.records:
        update = False
        b = False
        for comment in record["comments"]:
            if comment["content"] == "NetBox":
                b = True
                for ip in record["records"]:
                    record_ips.append(
                        (
                            record["name"],
                            record["type"],
                            ip["content"],
                            forward_zone_canonical,
                        )
                    )
            else:
                update = True
        else:
            if b == False:
                update = True
        if update:
            for ip in record["records"]:
                record_wo_comment_ips.append(
                    (
                        record["name"],
                        record["type"],
                        ip["content"],
                        forward_zone_canonical,
                    )
                )


for reverse_zone in REVERSE_ZONES:
    reverse_zone_canonical = reverse_zone.name + "."

    # get IPs within the prefix from NetBox
    records = nb.plugins.netbox_dns.records.filter(
        zone=reverse_zone.name, type__n=["NS", "SOA"]
    )

    # assemble list with tupels containing the canonical name, the record type
    # and the IP address without the subnet from NetBox IPs
    for record in records:
        host_ips.append(
            (
                record.name + "." + reverse_zone_canonical,
                record.type,
                record.value,
                reverse_zone_canonical,
            )
        )

    # get zone forward_zone_canonical form PowerDNS
    zone = pdns.get_zone(reverse_zone_canonical)

    # assemble list with tupels containing the canonical name, the record type,
    # the IP address and forward_zone_canonical without the subnet from
    # PowerDNS zone records with the
    # comment "NetBox"
    for record in zone.records:
        for comment in record["comments"]:
            if comment["content"] == "NetBox":
                for ip in record["records"]:
                    record_ips.append(
                        (
                            record["name"],
                            record["type"],
                            ip["content"],
                            reverse_zone_canonical,
                        )
                    )
        else:
            for ip in record["records"]:
                record_wo_comment_ips.append(
                    (
                        record["name"],
                        record["type"],
                        ip["content"],
                        reverse_zone_canonical,
                    )
                )

# create set with tupels that have to be created
# tupels from NetBox without tupels that already exists in PowerDNS
to_create = set(host_ips) - set(record_ips) - set(record_wo_comment_ips)

# create set with tupels that have to be updated
# tupels from NetBox that already exists in PowerDNS but dont have comment
to_update = set(host_ips) & set(record_wo_comment_ips)

# create set with tupels that have to be deleted
# tupels from PowerDNS without tupels that are documented in NetBox
to_delete = set(record_ips) - set(host_ips)

# create set with tupels that are missing
# tupels from PowerDNS that are not documented in NetBox
missing = set(record_wo_comment_ips) - set(record_ips) - set(host_ips)

print("----")

print(len(to_create), "records to create:")
for record in to_create:
    print(record[0])

print("----")

print(len(to_update), "records to update:")
for record in to_update:
    print(record[0])

print("----")

print(len(to_delete), "records to delete:")
for record in to_delete:
    print(record[0])

print("----")

print(len(missing), "missing records:")
for record in missing:
    print(record[0])

print("----")

for record in to_create:
    print("Creating", record)
    if not DEBUG:
        zone = pdns.get_zone(record[3])
        zone.create_records(
            [
                powerdns.RRSet(
                    record[0],
                    record[1],
                    [(record[2], False)],
                    comments=[powerdns.Comment("NetBox")],
                )
            ]
        )

print("----")

for record in to_update:
    print("Updating", record)
    if not DEBUG:
        zone = pdns.get_zone(record[3])
        zone.create_records(
            [
                powerdns.RRSet(
                    record[0],
                    record[1],
                    [(record[2], False)],
                    comments=[powerdns.Comment("NetBox")],
                )
            ]
        )

print("----")

for record in to_delete:
    print("Deleting", record)
    if not DEBUG:
        zone = pdns.get_zone(record[3])
        zone.delete_records(
            [
                powerdns.RRSet(
                    record[0],
                    record[1],
                    [(record[2], False)],
                    comments=[powerdns.Comment("NetBox")],
                )
            ]
        )

print("----")
