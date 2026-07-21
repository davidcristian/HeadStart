# VPC flow logs → CloudWatch. Captures accepted/rejected ENI traffic
# for incident response without changing the VPC data plane.

resource "aws_cloudwatch_log_group" "flow_log" {
  name              = "/vpc/${var.name}/flow-logs"
  retention_in_days = var.flow_log_retention_days
  tags              = merge(var.tags, { Name = "${var.name}-vpc-flow-logs" })
}

data "aws_iam_policy_document" "flow_log_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "flow_log" {
  name               = "${var.name}-vpc-flow-log"
  assume_role_policy = data.aws_iam_policy_document.flow_log_assume.json
  tags               = merge(var.tags, { Name = "${var.name}-vpc-flow-log" })
}

data "aws_iam_policy_document" "flow_log" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
    ]
    resources = [
      aws_cloudwatch_log_group.flow_log.arn,
      "${aws_cloudwatch_log_group.flow_log.arn}:*",
    ]
  }
}

resource "aws_iam_role_policy" "flow_log" {
  name   = "${var.name}-vpc-flow-log"
  role   = aws_iam_role.flow_log.id
  policy = data.aws_iam_policy_document.flow_log.json
}

resource "aws_flow_log" "this" {
  iam_role_arn    = aws_iam_role.flow_log.arn
  log_destination = aws_cloudwatch_log_group.flow_log.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.this.id
  tags            = merge(var.tags, { Name = "${var.name}-vpc-flow-log" })
}
