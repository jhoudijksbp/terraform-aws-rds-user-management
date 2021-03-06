data "archive_file" "rds_user_management_lambda_arch" {
  output_path = "${path.module}/lambda/rds_user_management.zip"
  source_dir  = "${path.module}/lambda/"
  type        = "zip"
}

module "rds_user_management_lambda" {
  source           = "github.com/schubergphilis/terraform-aws-mcaf-lambda?ref=v0.1.25"
  name             = "rds_user_management_lambda"
  create_policy    = false
  description      = "Lambda for managing users in RDS Aurora"
  filename         = data.archive_file.rds_user_management_lambda_arch.output_path
  handler          = "rds_user_management.main"
  role_arn         = module.rds_user_management_lambda_role.arn
  runtime          = "python3.8"
  subnet_ids       = var.subnet_ids
  timeout          = 60
  tags             = var.tags

  providers = {
    aws.lambda = aws
  }
}

# Execute the usermanagement Lamba
resource "aws_cloudformation_stack" "execute_lambda_user_management" {
    name               = "rds-user-management-lambda"
    timeout_in_minutes = 5
    tags               = var.tags
  
    template_body = <<EOF
  {
    "Description" : "Execute a Lambda and return the results",
    "Resources": {
      "ExecuteLambda": {
        "Type": "Custom::ExecuteLambda",
        "Properties": 
          ${jsonencode(
    merge(
      {
        "ServiceToken" = module.rds_user_management_lambda.arn
      },
      {
        "run_on_every_apply" = "${timestamp()}"
      },
    ),
    )}
      }
    },
    "Outputs": {
      ${join(
    ",",
    formatlist(
      "\"%s\":{\"Value\": {\"Fn::GetAtt\":[\"ExecuteLambda\", \"%s\"]}}",
      ["Value", "Error"],
      ["Value", "Error"],
    ),
  )}
    }
  }
  EOF

  depends_on = [
    aws_secretsmanager_secret_version.db_user_privs_secret_version,
    aws_secretsmanager_secret_version.db_user_secret_version,
    module.rds_user_management_lambda
  ]
}

data "aws_iam_policy_document" "rds_user_management_lambda_policy" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:ListSecrets",
      "secretsmanager:RotateSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecretVersionStage",
    ]

    resources = [
      "arn:aws:secretsmanager:*:*:secret:*"
    ]
  }

  statement {
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]

    resources = [
      "arn:aws:kms:*:*:key/${var.kms_key_id}"
    ]
  }


  statement {
    actions = [
      "secretsmanager:ListSecrets",
    ]

    resources = [
      "*"
    ]
  }

  statement {
    actions = [
      "secretsmanager:GetRandomPassword",
    ]

    resources = [
      "*"
    ]
  }

  statement {
    actions = [
      "rds:DescribeDBClusters",
      "rds:ListTagsForResource",
    ]

    resources = [
      "arn:aws:rds:*:*:*:*"
    ]
  }

  statement {
    actions = [
       "rds-db:connect",
    ]

    resources = [
      "arn:aws:rds-db:*:dbuser:*/*"
    ]
  }
}

module "rds_user_management_lambda_role" {
  source                = "github.com/schubergphilis/terraform-aws-mcaf-role?ref=v0.3.0"
  name                  = "rds_user_management_lambda_role"
  create_policy         = true
  postfix               = false
  principal_type        = "Service"
  principal_identifiers = ["lambda.amazonaws.com"]
  role_policy           = data.aws_iam_policy_document.rds_user_management_lambda_policy.json
  tags                  = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_user_management_lambda_policy_vpcaccess" {
  role       = module.rds_user_management_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "rds_user_management_lambda_policy_basic" {
  role       = module.rds_user_management_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
