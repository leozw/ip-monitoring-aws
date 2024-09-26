# AWS IP Monitoring App

This application collects and exposes AWS subnet and VPC IP metrics, allowing these metrics to be visualized in Grafana through Prometheus. The metrics include information about subnets, VPCs, allocated IPs, and more.

## Features

- **Subnet IP Monitoring**: Total IPs, used IPs, and IP usage percentages for subnets.
- **Elastic IP Limit**: Exposes the account's Elastic IP limits.
- **Security Group Rules**: Counts the rules associated with each security group.
- **VPC Peering Connections Monitoring**: Number of peering connections between VPCs.
- **Multi-Region Support**: Allows monitoring of multiple AWS regions simultaneously.

## Exposed Metrics

Below are the key metrics exposed by the application:

- **`eks_subnet_total_ips`**: Total IPs in a subnet.
- **`eks_subnet_available_ips`**: Available IPs in a subnet.
- **`aws_elastic_ips_limit`**: Limit of available Elastic IPs for the account.
- **`aws_security_group_rules`**: Number of rules associated with a security group.
- **`aws_subnet_cidr_changes`**: Changes in the CIDR of subnets.
- **`eks_subnet_used_ips`**: Used IPs in a subnet.
- **`eks_subnet_used_ips_percentage`**: Percentage of used IPs in a subnet.
- **`eks_subnet_cidr_size`**: Size of the subnet CIDR block.
- **`aws_vpc_peering_connections`**: Number of VPC peering connections.

## How to Run

### 1. EC2 with User Data (Better with Terraform *Step 4)

You can deploy the application on an EC2 instance using the **User Data** script provided. The user data script is located in the `user-data-ec2` folder of this repository. Follow these steps:

### Create the Role

You need to create an IAM Role and attach the **AmazonEC2ReadOnlyAccess** policy, which provides the necessary read-only permissions to monitor subnets and VPCs. Use the following AWS CLI commands:

1. **Create the IAM Role**:

```bash
aws iam create-role \
  --role-name IPMonitoring \
  --assume-role-policy-document file://Policy/policy.json
```

1. **Attach the `AmazonEC2ReadOnlyAccess` Policy**:

```bash
aws iam attach-role-policy \
  --role-name IPMonitoring \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess
```

This attaches the required read-only permissions for EC2 resources.

### Apply the Role and User Data to EC2

- When launching the EC2 instance, go to the **Advanced Configuration** section and paste the content from `user-data-ec2/user-data-ubuntu.sh` into the **User Data** field.
- In the instance configuration, select the **IAM Role** you just created.

Once the instance is up and running, the application will automatically start and expose the metrics on port **8000** via HTTP.

### 2. Running in Kubernetes

If you prefer to run the application in a Kubernetes cluster, follow these steps:

1. **Create the IAM Role** for Kubernetes:
    
    You can create an IAM Role and associate it with the Kubernetes Service Account. Since EKS automatically manages the trust relationship via the OIDC provider, you don’t need to manually define a trust policy. Just use the following command to create the Role:
    
    ```bash
    aws iam create-role \
      --role-name IPMonitoring \
      --assume-role-policy-document file://<(echo '{}')
    ```
    
2. **Attach the `AmazonEC2ReadOnlyAccess` Policy**:
    
    Attach the policy that grants read-only access to EC2 resources:
    
    ```bash
    aws iam attach-role-policy \
      --role-name IPMonitoring \
      --policy-arn arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess
    ```
    
3. **Get the IAM Role ARN**:
    
    You’ll need the ARN of the role to configure it in Kubernetes. Get the ARN with:
    
    ```bash
    aws iam get-role --role-name IPMonitoring --query "Role.Arn" --output text
    ```
    
4. **Configure the Kubernetes Service Account**:
    
    Update the **`Kubernetes/service-account.yaml`** file with the ARN of the IAM Role you created. Replace `<IAM_ROLE_ARN>` with your actual ARN:
    
    ```yaml
    apiVersion: v1
    kind: ServiceAccount
    metadata:
      name: ip-monitoring-service-account
      namespace: default
      annotations:
        eks.amazonaws.com/role-arn: "<IAM_ROLE_ARN>"
    ```
    
5. **Deploy in Kubernetes**:
    
    After configuring the Service Account, deploy the application in Kubernetes using:
    
    ```bash
    kubectl apply -k Kubernetes/
    ```

### 3. Running Locally

You can also run the application locally, using your AWS credentials configured with the AWS CLI (`aws configure`).

1. **Set up AWS CLI**:
    - Make sure your local AWS CLI is configured with valid credentials (`aws configure`).
2. **Run the Application**:
    - In the project directory, run:
    
    ```bash
    python main.py
    ```
    
    This will start the application locally and expose metrics on port **8000**.
    
3. **Environment Variables (Regions)**:
    - You can pass multiple AWS regions as command-line arguments when running the app:
    
    ```bash
    python main.py us-east-1 us-west-2
    ```
    
    Or set the regions using an environment variable:
    
    ```bash
    AWS_REGION="us-east-1,us-west-2" python main.py
    ```
### 4. Deploy EC2 using Terraform

If you prefer to use Terraform to provision the EC2 instance with all the required IAM Role and User Data configurations, follow these steps:

### Configure Terraform

1. **Navigate to the `Terraform` directory** where the `main.tf` file is already located.

```bash
cd Terraform
```

### Run Terraform

1. **Initialize Terraform** in the directory where the `main.tf` file is:

```bash
terraform init
```

1. **Check the execution plan** to ensure everything is configured correctly:

```bash
terraform plan
```

1. **Apply the plan** to create the resources:

```bash
terraform apply
```

This will provision an EC2 instance with the configured **IAM Role**, **EC2 read-only policy**, and execute the **User Data** script to start your application.

## 5. Scraping Metrics

Once the application is deployed, you need to configure your Prometheus server or OpenTelemetry Collector to scrape the metrics exposed by the application. The metrics are available on port **8000** of the instance where the application is running.

### Option 1: Scraping Metrics with Prometheus

To scrape the metrics directly with Prometheus, you need to add a scrape configuration to your `prometheus.yml` file. Here is an example configuration:

```yaml
scrape_configs:
  - job_name: 'aws-ip-monitoring'
    scrape_interval: 30s
    metrics_path: '/'
    static_configs:
      - targets: ['<SERVICE_IP_OR_NAME>:8000']
```

1. **Replace `<SERVICE_IP_OR_NAME>`** with the public or private IP of your EC2 instance where the app is running, or use the Kubernetes service name if running in a Kubernetes cluster.
2. **Restart Prometheus** after adding this configuration to ensure the changes take effect.

This will allow Prometheus to scrape the metrics every 30 seconds from your application.

### Option 2: Scraping Metrics with OpenTelemetry Collector

If you are using the OpenTelemetry Collector to aggregate metrics, configure the Collector to scrape the application. Below is an example configuration for the OpenTelemetry Collector:

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: 'aws-ip-monitoring'
          scrape_interval: 30s
          static_configs:
            - targets: ['<SERVICE_IP_OR_NAME>:8000']
```

1. **Replace `<SERVICE_IP_OR_NAME>`** with the public or private IP of your EC2 instance where the app is running, or use the Kubernetes service name if running in a Kubernetes cluster.

### Testing the Metrics

After configuring Prometheus or the OpenTelemetry Collector, you can verify that the metrics are being scraped by accessing the Prometheus UI or checking the logs of the OpenTelemetry Collector. You should see the AWS IP monitoring metrics available and ready for visualization in Grafana or any other monitoring tool.

## Prerequisites

- **Docker**: Required if you're running the app on EC2 or Kubernetes.
- **Python**: Required if you're running the app locally (Python 3.7+).
- **AWS Credentials**: Ensure your AWS credentials have permissions to describe subnets, VPCs, and Elastic IPs.
- **Prometheus** or **OpenTelemetry Collector**: Required for scraping the metrics exposed by the application.
- **Grafana**: Recommended for visualizing the metrics once scraped.

## Folder Structure

- **`Dockerfile`**: Dockerfile to build the application image.
- **`Kubernetes/`**: Kubernetes configuration files to run the application in a cluster.
- **`user-data-ec2/`**: User data script to run the application directly on EC2 instances.
- **`Policy/`**: IAM policies needed to run the application.
- **`main.py`**: The main Python script that collects and exposes the metrics.

## References

- [AWS IAM Documentation](https://docs.aws.amazon.com/iam/)
- Prometheus Metrics
- Docker Documentation
- Kubernetes Documentation