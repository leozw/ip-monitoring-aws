provider "aws" {
  region = "us-east-1"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] 
}

resource "aws_iam_role" "ec2_role" {
  name = "IPMonitoringEC2Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "ec2.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_readonly" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess"
}

resource "aws_iam_instance_profile" "ec2_instance_profile" {
  name = "IPMonitoringEC2Profile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_key_pair" "key_pair" {
  key_name   = "MyKeyPair"
  public_key = file("~/.ssh/id_rsa.pub")
}

data "template_file" "user_data" {
  template = file("../user-data-ec2/user-data-ubuntu.sh")
}

resource "aws_instance" "ip_monitoring_ec2" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t2.micro"
  key_name               = aws_key_pair.key_pair.key_name
  iam_instance_profile   = aws_iam_instance_profile.ec2_instance_profile.name
  user_data              = data.template_file.user_data.rendered

  tags = {
    Name = "IPMonitoringInstance"
  }
}
