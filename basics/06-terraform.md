# 6. Terraform

Terraform compares three things: your code, its state file and the real world. Most incidents come from those three disagreeing.

This first lab needs no cloud account. `terraform_data` is built into Terraform and OpenTofu, so you can learn the workflow with nothing at risk.

## Do it

Create `main.tf` in an empty folder:

```hcl
variable "environment" {
  type    = string
  default = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

resource "terraform_data" "release" {
  input = {
    environment = var.environment
    replicas    = var.environment == "prod" ? 3 : 1
  }
}

output "release" {
  value = terraform_data.release.output
}
```

```bash
terraform init
terraform plan
terraform apply -auto-approve
cat terraform.tfstate
terraform apply -auto-approve -var environment=prod   # Read the plan before it applies.
terraform state list
terraform state show terraform_data.release
```

## Break it

```bash
# Validation stops a bad value before anything changes.
terraform plan -var environment=staging

# Lost state: Terraform forgets what it created.
mv terraform.tfstate saved.tfstate
terraform plan              # Wants to create it again.
mv saved.tfstate terraform.tfstate

# Replace on purpose.
terraform apply -auto-approve -replace=terraform_data.release
```

## Build your own

The next step is yours to write, not to copy. Build this in [`projects/`](../projects) as `02-cloud-network`:

1. Create a free personal cloud account. Do not use an employer's tenancy.
2. Write a module for a network with one public and one private subnet.
3. Store state in a remote backend with locking.
4. Change a setting by hand in the console, then use `terraform plan` to detect the drift.
5. Bring a manually created resource under management with an `import` block.
6. Run `terraform destroy` and confirm in the console that nothing remains.

## Explain it

- What is in the state file, and why must it never go into Git?
- What happens if someone changes a resource in the console?
- What is the difference between `count` and `for_each`, and why is `for_each` usually safer?
- How would you rename a resource without destroying it?
- How do you split `dev` and `prod` so a mistake in one cannot touch the other?
- A `terraform apply` failed halfway. What state are you in, and what do you do?

## Done when

You can read a plan and say exactly what will be created, changed or destroyed, and why, before you approve it.
