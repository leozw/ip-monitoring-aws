import ipaddress
import os
import sys
import time

import boto3
from prometheus_client import Gauge, start_http_server

regions = sys.argv[1:] if len(sys.argv) > 1 else os.getenv('AWS_REGION', 'us-east-1,us-west-2,sa-east-1').split(',')

total_ips_gauge = Gauge('eks_subnet_total_ips', 'Total IPs in the subnet', ['subnet_id', 'vpc_id', 'environment', 'availability_zone', 'region', 'tags'])
available_ips_gauge = Gauge('eks_subnet_available_ips', 'Available IPs in the subnet', ['subnet_id', 'vpc_id', 'environment', 'availability_zone', 'region', 'tags'])
elastic_ips_gauge = Gauge('aws_elastic_ips_limit', 'Limit of available Elastic IPs', ['region'])
security_group_gauge = Gauge('aws_security_group_rules', 'Number of rules associated with the Security Group', ['security_group_id', 'subnet_id', 'environment', 'region'])
subnet_changes_gauge = Gauge('aws_subnet_cidr_changes', 'Changes in the CIDR block of the subnets', ['subnet_id', 'vpc_id', 'old_cidr', 'new_cidr', 'region'])
used_ips_gauge = Gauge('eks_subnet_used_ips', 'Used IPs in the subnet', ['subnet_id', 'vpc_id', 'environment', 'availability_zone', 'region', 'tags'])
used_ips_percentage_gauge = Gauge('eks_subnet_used_ips_percentage', 'Percentage of used IPs in the subnet', ['subnet_id', 'vpc_id', 'environment', 'availability_zone', 'region', 'tags'])
subnet_cidr_size_gauge = Gauge('eks_subnet_cidr_size', 'Size of the subnet CIDR block', ['subnet_id', 'vpc_id', 'environment', 'availability_zone', 'region', 'tags'])
vpc_peering_connections_gauge = Gauge('aws_vpc_peering_connections', 'Number of VPC peering connections', ['vpc_id', 'region'])

previous_cidr = {}

def collect_vpc_peering_connections(ec2, region):
    vpcs = ec2.describe_vpcs()['Vpcs']
    for vpc in vpcs:
        vpc_id = vpc['VpcId']
        peering_connections = ec2.describe_vpc_peering_connections(Filters=[{'Name': 'requester-vpc-info.vpc-id', 'Values': [vpc_id]}])['VpcPeeringConnections']
        num_connections = len(peering_connections)
        vpc_peering_connections_gauge.labels(vpc_id=vpc_id, region=region).set(num_connections)

def collect_subnet_cidr_size_metrics(ec2, region):
    subnets = ec2.describe_subnets()['Subnets']
    for subnet in subnets:
        subnet_id = subnet['SubnetId']
        vpc_id = subnet['VpcId']
        cidr_block = subnet['CidrBlock']
        cidr_size = ipaddress.ip_network(cidr_block).prefixlen  
        tags = format_tags(subnet.get('Tags', []))
        environment = get_environment_from_tags(subnet.get('Tags', []))
        availability_zone = subnet['AvailabilityZone']
        
        subnet_cidr_size_gauge.labels(subnet_id=subnet_id, vpc_id=vpc_id, environment=environment, availability_zone=availability_zone, region=region, tags=tags).set(cidr_size)

def collect_used_ips_percentage_metrics(ec2, region):
    subnets = ec2.describe_subnets()['Subnets']
    for subnet in subnets:
        subnet_id = subnet['SubnetId']
        vpc_id = subnet['VpcId']
        total_ips = calculate_total_ips(subnet['CidrBlock'])
        available_ips = subnet['AvailableIpAddressCount']
        used_ips_percentage = ((total_ips - available_ips) / total_ips) * 100
        tags = format_tags(subnet.get('Tags', []))
        environment = get_environment_from_tags(subnet.get('Tags', []))
        availability_zone = subnet['AvailabilityZone']
        
        used_ips_percentage_gauge.labels(subnet_id=subnet_id, vpc_id=vpc_id, environment=environment, availability_zone=availability_zone, region=region, tags=tags).set(used_ips_percentage)

def collect_used_ips_metrics(ec2, region):
    subnets = ec2.describe_subnets()['Subnets']
    for subnet in subnets:
        subnet_id = subnet['SubnetId']
        vpc_id = subnet['VpcId']
        total_ips = calculate_total_ips(subnet['CidrBlock'])
        available_ips = subnet['AvailableIpAddressCount']
        used_ips = total_ips - available_ips
        tags = format_tags(subnet.get('Tags', []))
        environment = get_environment_from_tags(subnet.get('Tags', []))
        availability_zone = subnet['AvailabilityZone']
        
        used_ips_gauge.labels(subnet_id=subnet_id, vpc_id=vpc_id, environment=environment, availability_zone=availability_zone, region=region, tags=tags).set(used_ips)

def calculate_total_ips(cidr_block):
    network = ipaddress.ip_network(cidr_block)
    return network.num_addresses  

def format_tags(tags):
    if tags:
        return ",".join([f"{tag['Key']}={tag['Value']}" for tag in tags])
    return "no-tags"

def get_environment_from_tags(tags):
    for tag in tags:
        if tag['Key'] == 'Environment':  
            return tag['Value']
    return 'Unknown'

def collect_subnet_metrics(ec2, region):
    subnets = ec2.describe_subnets()['Subnets']
    for subnet in subnets:
        subnet_id = subnet['SubnetId']
        vpc_id = subnet['VpcId']
        cidr_block = subnet['CidrBlock']
        available_ips = subnet['AvailableIpAddressCount']
        availability_zone = subnet['AvailabilityZone']  
        
        tags = subnet.get('Tags', [])
        formatted_tags = format_tags(tags)
        
        environment = get_environment_from_tags(tags)
        
        total_ips = calculate_total_ips(cidr_block)
        
        total_ips_gauge.labels(subnet_id=subnet_id, vpc_id=vpc_id, environment=environment, availability_zone=availability_zone, region=region, tags=formatted_tags).set(total_ips)
        available_ips_gauge.labels(subnet_id=subnet_id, vpc_id=vpc_id, environment=environment, availability_zone=availability_zone, region=region, tags=formatted_tags).set(available_ips)


def collect_limits_metrics(ec2, region):
    account_attributes = ec2.describe_account_attributes()
    for attribute in account_attributes['AccountAttributes']:
        if attribute['AttributeName'] == 'vpc-max-elastic-ips':
            elastic_ips_limit = int(attribute['AttributeValues'][0]['AttributeValue'])
            elastic_ips_gauge.labels(region=region).set(elastic_ips_limit)

def collect_security_group_metrics(ec2, region):
    instances = ec2.describe_instances()
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            if 'SubnetId' in instance:
                subnet_id = instance['SubnetId']
                environment = get_environment_from_tags(instance.get('Tags', []))
                
                for sg in instance['SecurityGroups']:
                    sg_id = sg['GroupId']
                    sg_info = ec2.describe_security_groups(GroupIds=[sg_id])
                    num_rules = len(sg_info['SecurityGroups'][0]['IpPermissions'])
                    
                    security_group_gauge.labels(security_group_id=sg_id, subnet_id=subnet_id, region=region, environment=environment).set(num_rules)

def track_subnet_changes(ec2, region):
    subnets = ec2.describe_subnets()['Subnets']
    for subnet in subnets:
        subnet_id = subnet['SubnetId']
        vpc_id = subnet['VpcId']
        cidr_block = subnet['CidrBlock']
        
        if subnet_id in previous_cidr and previous_cidr[subnet_id] != cidr_block:
            subnet_changes_gauge.labels(subnet_id=subnet_id, vpc_id=vpc_id, region=region, old_cidr=previous_cidr[subnet_id], new_cidr=cidr_block).set(1)
        
        previous_cidr[subnet_id] = cidr_block

def collect_metrics():
    for region in regions:
        ec2 = boto3.client('ec2', region_name=region)
        collect_subnet_metrics(ec2, region)
        collect_limits_metrics(ec2, region)
        collect_security_group_metrics(ec2, region)
        collect_used_ips_metrics(ec2, region)
        collect_used_ips_percentage_metrics(ec2, region)
        collect_subnet_cidr_size_metrics(ec2, region)
        collect_vpc_peering_connections(ec2, region)
        track_subnet_changes(ec2, region)

if __name__ == '__main__':
    start_http_server(8000)
    
    while True:
        collect_metrics()
        time.sleep(300) 
