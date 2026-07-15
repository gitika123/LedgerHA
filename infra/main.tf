terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "project" {
  type    = string
  default = "ledgerha"
}

variable "db_name" {
  type    = string
  default = "ledgerha"
}

variable "db_username" {
  type    = string
  default = "ledger_admin"
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

resource "random_password" "db" {
  length  = 20
  special = false
}

resource "aws_vpc" "main" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "${var.project}-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project}-igw" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project}-public-a" }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.20.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project}-public-b" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.20.11.0/24"
  availability_zone = "${var.aws_region}a"
  tags              = { Name = "${var.project}-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.20.12.0/24"
  availability_zone = "${var.aws_region}b"
  tags              = { Name = "${var.project}-private-b" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "${var.project}-public-rt" }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_db_subnet_group" "db" {
  name       = "${var.project}-db-subnets"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  tags       = { Name = "${var.project}-db-subnets" }
}

resource "aws_security_group" "db" {
  name        = "${var.project}-db-sg"
  description = "PostgreSQL from app SG only"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  name        = "${var.project}-app-sg"
  description = "App hosts that may talk to RDS"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_secretsmanager_secret" "db" {
  name = "${var.project}-db-credentials"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    engine   = "postgres"
    dbname   = var.db_name
    host     = aws_db_instance.postgres.address
    port     = 5432
  })
}

# Multi-AZ synchronous standby for automatic failover
resource "aws_db_instance" "postgres" {
  identifier                  = "${var.project}-postgres"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = var.db_instance_class
  allocated_storage           = 20
  max_allocated_storage       = 100
  db_name                     = var.db_name
  username                    = var.db_username
  password                    = random_password.db.result
  db_subnet_group_name        = aws_db_subnet_group.db.name
  vpc_security_group_ids      = [aws_security_group.db.id]
  multi_az                    = true
  storage_encrypted           = true
  backup_retention_period     = 7
  skip_final_snapshot         = true
  publicly_accessible         = false
  deletion_protection         = false
  apply_immediately           = true
  tags = {
    Name        = "${var.project}-postgres"
    Application = "LedgerHA"
  }
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}

output "rds_port" {
  value = aws_db_instance.postgres.port
}

output "db_secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "app_security_group_id" {
  value = aws_security_group.app.id
}

output "database_url_hint" {
  value = "postgresql+psycopg://${var.db_username}:<from-secrets>@${aws_db_instance.postgres.address}:5432/${var.db_name}"
}
