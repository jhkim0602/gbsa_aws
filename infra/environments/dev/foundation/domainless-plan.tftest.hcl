# The foundation root planned with the values dev is actually applied with.
#
# There was no test at this level, and the gap was not theoretical: with `sender_address` and
# `company_domain` both null -- the committed dev configuration -- the identity module failed
# during evaluation of its own locals, before the precondition written to explain that case
# could run. `terraform validate` accepts it, because the values are only known at plan.
#
# So this planning the root at all is most of the point. The assertions below then pin the two
# things a domainless environment gets wrong quietly rather than loudly.

mock_provider "aws" {}

# The committed dev values, so this exercises the configuration that is actually applied
# rather than a shape invented for the test.
variables {
  environment_name      = "dev"
  cognito_domain_prefix = "iep-dev-company-868216907365"
}

run "dev_plans_before_a_mailbox_has_been_chosen" {
  command = plan

  override_data {
    target = module.network.data.aws_availability_zones.available
    values = {
      names = ["ap-northeast-2a", "ap-northeast-2c"]
    }
  }

  override_data {
    target = module.network.data.aws_region.current
    values = {
      name = "ap-northeast-2"
    }
  }

  override_data {
    target = module.identity.data.aws_region.current
    values = {
      name = "ap-northeast-2"
    }
  }

  variables {
    sender_address    = null
    console_base_urls = ["http://localhost:5173"]
  }

  # Nothing to send from, and therefore nothing that claims otherwise: no identity to verify,
  # and a null From rather than a `noreply@null` that would be accepted as a string and
  # rejected by SES at the first invitation.
  assert {
    condition = alltrue([
      output.identity.email_identity == null,
      output.identity.from_address == null,
    ])
    error_message = "an environment with no sender_address must report no mail identity at all"
  }

  # The pool is the half that must exist regardless: it is created here, its custom attributes
  # can never be added later, and the console can log in against it from a workstation long
  # before mail works. Asserted through the schema rather than the id, which Cognito assigns at
  # apply and is null in any plan.
  assert {
    condition = length([
      for name in module.identity.pool_schema_names :
      name if contains(["company_id", "company_user_id"], name)
    ]) == 2
    error_message = "the user pool and its tenant attributes are not conditional on mail being configured"
  }

  # A hosted login domain, because the console sends the user to `/oauth2/authorize` on it and
  # a pool without one has no such endpoint -- the console would fall back to a demo token the
  # deployed API rejects.
  assert {
    condition = (
      output.identity.user_pool_login_domain == null
      ? false
      : strcontains(output.identity.user_pool_login_domain, ".auth.ap-northeast-2.amazoncognito.com")
    )
    error_message = "dev needs a hosted Cognito login domain to log in through a browser"
  }

  # What the operator is told to do next. Null here, with mail unconfigured, would be a
  # deployment that silently cannot send.
  assert {
    condition     = output.manual_verification.next_step != null
    error_message = "the root must state the remaining manual step"
  }
}

run "a_verified_address_makes_the_environment_able_to_send" {
  command = plan

  override_data {
    target = module.network.data.aws_availability_zones.available
    values = {
      names = ["ap-northeast-2a", "ap-northeast-2c"]
    }
  }

  override_data {
    target = module.network.data.aws_region.current
    values = {
      name = "ap-northeast-2"
    }
  }

  override_data {
    target = module.identity.data.aws_region.current
    values = {
      name = "ap-northeast-2"
    }
  }

  variables {
    sender_address    = "interviews@example.test"
    console_base_urls = ["http://localhost:5173"]
  }

  assert {
    condition = alltrue([
      output.identity.email_identity == "interviews@example.test",
      output.identity.from_address == "interviews@example.test",
    ])
    error_message = "the address given is both the identity verified and the From used"
  }

  # The application root reads this to build SES_FROM_ADDRESS, which the API requires at
  # startup, so it must be a sendable address and not a domain-shaped placeholder.
  assert {
    condition     = strcontains(output.identity.from_address, "@")
    error_message = "from_address must be an address the API can send as"
  }
}
