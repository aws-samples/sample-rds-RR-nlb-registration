"""Structural correctness tests for the CloudFormation template.

These tests validate the JSON structure of the CloudFormation template
without deploying it or importing any AWS libraries.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def template():
    """Load and parse the CloudFormation template JSON."""
    template_path = (
        Path(__file__).resolve().parent.parent
        / "infrastructure"
        / "cloudformation_NLB_TG_with_RDS_RR.json"
    )
    assert template_path.exists(), f"Template not found at {template_path}"
    with open(template_path, "r") as f:
        return json.load(f)


class TestTemplateValidity:
    """Verify the template is valid JSON with required top-level keys."""

    def test_template_has_required_top_level_keys(self, template):
        """The template must contain Parameters, Conditions, Resources, Metadata, and Outputs."""
        required_keys = {"Parameters", "Conditions", "Resources", "Metadata", "Outputs"}
        missing = required_keys - set(template.keys())
        assert not missing, f"Template is missing required top-level keys: {missing}"

    def test_template_has_description(self, template):
        """The template should have a Description field."""
        assert "Description" in template

    def test_template_has_aws_template_format_version(self, template):
        """The template should declare a valid AWSTemplateFormatVersion."""
        assert "AWSTemplateFormatVersion" in template
        assert template["AWSTemplateFormatVersion"] == "2010-09-09"


class TestCreateFlagParametersAndConditions:
    """Verify Create* flag parameters and their corresponding Conditions.

    Validates: Design Property 3 (Create Flag Parameter Consistency)
    Requirements: 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2
    """

    CREATE_FLAGS = ["CreateNLB", "CreateTargetGroup", "CreateS3Bucket", "CreateRDSReplica"]

    def test_all_create_parameters_exist(self, template):
        """All 4 Create* parameters must exist in the template."""
        params = template["Parameters"]
        for flag in self.CREATE_FLAGS:
            assert flag in params, f"Parameter '{flag}' is missing from the template"

    def test_create_parameters_have_correct_allowed_values(self, template):
        """Each Create* parameter must have AllowedValues ["true", "false"]."""
        params = template["Parameters"]
        for flag in self.CREATE_FLAGS:
            param = params[flag]
            assert "AllowedValues" in param, f"Parameter '{flag}' missing AllowedValues"
            assert sorted(param["AllowedValues"]) == ["false", "true"], (
                f"Parameter '{flag}' AllowedValues should be ['true', 'false'], "
                f"got {param['AllowedValues']}"
            )

    def test_create_parameters_default_to_false(self, template):
        """Each Create* parameter must default to "false"."""
        params = template["Parameters"]
        for flag in self.CREATE_FLAGS:
            param = params[flag]
            assert "Default" in param, f"Parameter '{flag}' missing Default"
            assert param["Default"] == "false", (
                f"Parameter '{flag}' Default should be 'false', got '{param['Default']}'"
            )

    def test_all_conditions_exist(self, template):
        """All 4 Create*Condition conditions must exist."""
        conditions = template["Conditions"]
        expected_conditions = [
            "CreateNLBCondition",
            "CreateTargetGroupCondition",
            "CreateS3BucketCondition",
            "CreateRDSReplicaCondition",
        ]
        for cond in expected_conditions:
            assert cond in conditions, f"Condition '{cond}' is missing from the template"

    def test_conditions_use_fn_equals_referencing_parameters(self, template):
        """Each condition must use Fn::Equals comparing its corresponding parameter to "true"."""
        conditions = template["Conditions"]
        flag_to_condition = {
            "CreateNLB": "CreateNLBCondition",
            "CreateTargetGroup": "CreateTargetGroupCondition",
            "CreateS3Bucket": "CreateS3BucketCondition",
            "CreateRDSReplica": "CreateRDSReplicaCondition",
        }
        for param_name, cond_name in flag_to_condition.items():
            cond = conditions[cond_name]
            assert "Fn::Equals" in cond, (
                f"Condition '{cond_name}' must use Fn::Equals"
            )
            fn_equals = cond["Fn::Equals"]
            assert len(fn_equals) == 2, (
                f"Condition '{cond_name}' Fn::Equals must have exactly 2 elements"
            )
            # First element should be a Ref to the parameter
            assert fn_equals[0] == {"Ref": param_name}, (
                f"Condition '{cond_name}' should reference parameter '{param_name}', "
                f"got {fn_equals[0]}"
            )
            # Second element should be "true"
            assert fn_equals[1] == "true", (
                f"Condition '{cond_name}' should compare to 'true', got '{fn_equals[1]}'"
            )

    def test_create_nlb_and_target_group_condition_exists(self, template):
        """CreateNLBAndTargetGroupCondition must exist with Fn::And expression."""
        conditions = template["Conditions"]
        cond_name = "CreateNLBAndTargetGroupCondition"
        assert cond_name in conditions, f"Condition '{cond_name}' is missing"
        cond = conditions[cond_name]
        assert "Fn::And" in cond, (
            f"Condition '{cond_name}' must use Fn::And"
        )
        fn_and = cond["Fn::And"]
        assert len(fn_and) == 2, (
            f"Condition '{cond_name}' Fn::And must have exactly 2 elements"
        )
        # Verify it references both conditions
        referenced_conditions = {
            item["Condition"] for item in fn_and if "Condition" in item
        }
        assert "CreateNLBCondition" in referenced_conditions, (
            f"Condition '{cond_name}' must reference CreateNLBCondition"
        )
        assert "CreateTargetGroupCondition" in referenced_conditions, (
            f"Condition '{cond_name}' must reference CreateTargetGroupCondition"
        )


class TestFnIfResolution:
    """Verify Fn::If expressions resolve with the correct condition names.

    Validates: Design Properties 2, 5, 6
    Requirements: 3.6, 3.7, 4.5, 4.6, 6.1, 6.3, 6.4
    """

    def test_lambda_nlb_tg_arn_uses_fn_if_with_create_target_group_condition(self, template):
        """Lambda NLB_TG_ARN env var uses Fn::If with CreateTargetGroupCondition."""
        env_vars = template["Resources"]["LambdaFunction"]["Properties"]["Environment"]["Variables"]
        nlb_tg_arn = env_vars["NLB_TG_ARN"]
        assert "Fn::If" in nlb_tg_arn
        assert nlb_tg_arn["Fn::If"][0] == "CreateTargetGroupCondition"

    def test_lambda_s3_bucket_uses_fn_if_with_create_s3_bucket_condition(self, template):
        """Lambda S3_BUCKET env var uses Fn::If with CreateS3BucketCondition."""
        env_vars = template["Resources"]["LambdaFunction"]["Properties"]["Environment"]["Variables"]
        s3_bucket = env_vars["S3_BUCKET"]
        assert "Fn::If" in s3_bucket
        assert s3_bucket["Fn::If"][0] == "CreateS3BucketCondition"

    def test_iam_policy_elb_target_group_resource_uses_fn_if_with_create_target_group_condition(self, template):
        """IAM policy ELBTargetGroup statement Resource uses Fn::If with CreateTargetGroupCondition."""
        statements = template["Resources"]["LambdaRDSReadReplicaPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        elb_tg_statement = next(s for s in statements if s.get("Sid") == "ELBTargetGroup")
        resource = elb_tg_statement["Resource"]
        assert "Fn::If" in resource
        assert resource["Fn::If"][0] == "CreateTargetGroupCondition"

    def test_iam_policy_s3_statement_resources_use_fn_if_with_create_s3_bucket_condition(self, template):
        """IAM policy S3 statement Resources use Fn::If with CreateS3BucketCondition."""
        statements = template["Resources"]["LambdaRDSReadReplicaPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        s3_statement = next(s for s in statements if s.get("Sid") == "S3")
        resources = s3_statement["Resource"]
        assert isinstance(resources, list)
        for resource_item in resources:
            assert "Fn::If" in resource_item
            assert resource_item["Fn::If"][0] == "CreateS3BucketCondition"


class TestConditionalResources:
    """Verify conditional resources have correct Condition keys and expected properties.

    **Validates: Design Property 1 (Condition Coverage)**
    **Requirements: 2.3, 3.3, 3.4, 4.3, 5.3, 6.2**
    """

    # --- Condition key assertions ---

    def test_nlb_has_correct_condition(self, template):
        """NetworkLoadBalancer must have Condition = CreateNLBCondition."""
        resource = template["Resources"]["NetworkLoadBalancer"]
        assert resource["Condition"] == "CreateNLBCondition"

    def test_target_group_has_correct_condition(self, template):
        """NLBTargetGroup must have Condition = CreateTargetGroupCondition."""
        resource = template["Resources"]["NLBTargetGroup"]
        assert resource["Condition"] == "CreateTargetGroupCondition"

    def test_nlb_listener_has_correct_condition(self, template):
        """NLBListener must have Condition = CreateNLBAndTargetGroupCondition."""
        resource = template["Resources"]["NLBListener"]
        assert resource["Condition"] == "CreateNLBAndTargetGroupCondition"

    def test_state_bucket_has_correct_condition(self, template):
        """StateBucket must have Condition = CreateS3BucketCondition."""
        resource = template["Resources"]["StateBucket"]
        assert resource["Condition"] == "CreateS3BucketCondition"

    def test_rds_read_replica_has_correct_condition(self, template):
        """RDSReadReplica must have Condition = CreateRDSReplicaCondition."""
        resource = template["Resources"]["RDSReadReplica"]
        assert resource["Condition"] == "CreateRDSReplicaCondition"

    # --- NLB resource properties ---

    def test_nlb_type_is_network(self, template):
        """NLB must have Type property set to 'network'."""
        props = template["Resources"]["NetworkLoadBalancer"]["Properties"]
        assert props["Type"] == "network"

    def test_nlb_references_subnet_ids_and_scheme(self, template):
        """NLB must reference NLBSubnetIds and NLBScheme parameters."""
        props = template["Resources"]["NetworkLoadBalancer"]["Properties"]
        assert props["Subnets"] == {"Ref": "NLBSubnetIds"}
        assert props["Scheme"] == {"Ref": "NLBScheme"}

    # --- Target Group resource properties ---

    def test_target_group_target_type_is_ip(self, template):
        """Target Group must have TargetType 'ip'."""
        props = template["Resources"]["NLBTargetGroup"]["Properties"]
        assert props["TargetType"] == "ip"

    def test_target_group_protocol_is_tcp(self, template):
        """Target Group must use Protocol TCP."""
        props = template["Resources"]["NLBTargetGroup"]["Properties"]
        assert props["Protocol"] == "TCP"

    def test_target_group_references_rds_port_and_vpc(self, template):
        """Target Group must reference RDSListenerPort and VpcId parameters."""
        props = template["Resources"]["NLBTargetGroup"]["Properties"]
        assert props["Port"] == {"Ref": "RDSListenerPort"}
        assert props["VpcId"] == {"Ref": "VpcId"}

    # --- S3 Bucket resource properties ---

    def test_s3_bucket_has_block_public_access(self, template):
        """StateBucket must have PublicAccessBlockConfiguration with all settings true."""
        props = template["Resources"]["StateBucket"]["Properties"]
        public_access = props["PublicAccessBlockConfiguration"]
        assert public_access["BlockPublicAcls"] is True
        assert public_access["BlockPublicPolicy"] is True
        assert public_access["IgnorePublicAcls"] is True
        assert public_access["RestrictPublicBuckets"] is True

    def test_s3_bucket_has_encryption(self, template):
        """StateBucket must have server-side encryption configured."""
        props = template["Resources"]["StateBucket"]["Properties"]
        encryption = props["BucketEncryption"]["ServerSideEncryptionConfiguration"]
        assert len(encryption) > 0
        sse_default = encryption[0]["ServerSideEncryptionByDefault"]
        assert sse_default["SSEAlgorithm"] == "AES256"

    def test_s3_bucket_has_versioning(self, template):
        """StateBucket must have versioning enabled."""
        props = template["Resources"]["StateBucket"]["Properties"]
        versioning = props["VersioningConfiguration"]
        assert versioning["Status"] == "Enabled"

    # --- RDS Read Replica resource properties ---

    def test_rds_replica_has_source_db_identifier(self, template):
        """RDSReadReplica must have SourceDBInstanceIdentifier property."""
        props = template["Resources"]["RDSReadReplica"]["Properties"]
        assert "SourceDBInstanceIdentifier" in props

    # --- NLB Listener condition (explicit re-check) ---

    def test_nlb_listener_has_combined_condition(self, template):
        """NLBListener must use CreateNLBAndTargetGroupCondition (both NLB and TG required)."""
        resource = template["Resources"]["NLBListener"]
        assert resource["Condition"] == "CreateNLBAndTargetGroupCondition"


class TestMetadataAndOutputs:
    """Verify Metadata interface completeness and Output condition correctness.

    Validates: Design Properties 4, 7
    Requirements: 5.7, 6.5, 7.2
    """

    def test_every_parameter_in_at_least_one_interface_group(self, template):
        """Every parameter must appear in at least one AWS::CloudFormation::Interface parameter group."""
        all_params = set(template["Parameters"].keys())
        groups = template["Metadata"]["AWS::CloudFormation::Interface"]["ParameterGroups"]
        grouped_params = set()
        for group in groups:
            grouped_params.update(group["Parameters"])

        missing = all_params - grouped_params
        assert not missing, (
            f"Parameters not in any ParameterGroup: {sorted(missing)}"
        )

    def test_conditional_outputs_have_correct_condition_keys(self, template):
        """Conditional outputs must reference the correct Condition."""
        expected_conditions = {
            "NLBArn": "CreateNLBCondition",
            "NLBDNSName": "CreateNLBCondition",
            "TargetGroupArn": "CreateTargetGroupCondition",
            "StateBucketName": "CreateS3BucketCondition",
            "RDSReplicaEndpoint": "CreateRDSReplicaCondition",
        }
        outputs = template["Outputs"]
        for output_name, expected_condition in expected_conditions.items():
            assert output_name in outputs, f"Output '{output_name}' not found"
            assert "Condition" in outputs[output_name], (
                f"Output '{output_name}' is missing a Condition key"
            )
            assert outputs[output_name]["Condition"] == expected_condition, (
                f"Output '{output_name}' has Condition "
                f"'{outputs[output_name]['Condition']}', expected '{expected_condition}'"
            )

    def test_always_on_outputs_exist_without_condition(self, template):
        """Always-on outputs must exist and must NOT have a Condition key."""
        always_on_outputs = [
            "LambdaFunctionArn",
            "EffectiveTargetGroupArn",
            "EffectiveBucketName",
        ]
        outputs = template["Outputs"]
        for output_name in always_on_outputs:
            assert output_name in outputs, f"Output '{output_name}' not found"
            assert "Condition" not in outputs[output_name], (
                f"Output '{output_name}' should not have a Condition key"
            )


class TestConditionalResourceIsolation:
    """Verify unconditional resources do not reference conditional resources outside Fn::If.

    Resources with a Condition key must not be referenced (via Ref or Fn::GetAtt)
    from an unconditional context unless wrapped in an Fn::If that gates on the
    same condition. This ensures CloudFormation never attempts to resolve attributes
    of uncreated resources.

    Validates: Design Property 8 (Conditional Resource Isolation)
    Requirements: 2.4, 3.5, 4.4, 5.4
    """

    def _get_conditional_resources(self, template):
        """Return set of logical IDs for resources that have a Condition key."""
        return {
            logical_id
            for logical_id, resource in template["Resources"].items()
            if "Condition" in resource
        }

    def _get_unconditional_resources(self, template):
        """Return set of logical IDs for resources without a Condition key."""
        return {
            logical_id
            for logical_id, resource in template["Resources"].items()
            if "Condition" not in resource
        }

    def _find_unguarded_refs(self, node, conditional_resources, inside_fn_if=False):
        """Recursively walk a JSON structure and find unguarded references to conditional resources.

        Returns a list of (ref_type, resource_id) tuples for any Ref or Fn::GetAtt
        that references a conditional resource without being inside an Fn::If.
        """
        violations = []

        if isinstance(node, dict):
            # Check if this dict is an Fn::If — children are guarded
            if "Fn::If" in node:
                fn_if_value = node["Fn::If"]
                if isinstance(fn_if_value, list) and len(fn_if_value) == 3:
                    # The condition name is element 0, then-branch is element 1,
                    # else-branch is element 2. Both branches are inside Fn::If.
                    # Recurse into then and else branches with inside_fn_if=True
                    violations.extend(
                        self._find_unguarded_refs(fn_if_value[1], conditional_resources, inside_fn_if=True)
                    )
                    violations.extend(
                        self._find_unguarded_refs(fn_if_value[2], conditional_resources, inside_fn_if=True)
                    )
                # Also check other keys in this dict (besides Fn::If)
                for key, value in node.items():
                    if key != "Fn::If":
                        violations.extend(
                            self._find_unguarded_refs(value, conditional_resources, inside_fn_if)
                        )
                return violations

            # Check for Ref to a conditional resource
            if "Ref" in node and node["Ref"] in conditional_resources and not inside_fn_if:
                violations.append(("Ref", node["Ref"]))

            # Check for Fn::GetAtt to a conditional resource
            if "Fn::GetAtt" in node:
                get_att = node["Fn::GetAtt"]
                if isinstance(get_att, list) and len(get_att) >= 1:
                    if get_att[0] in conditional_resources and not inside_fn_if:
                        violations.append(("Fn::GetAtt", get_att[0]))
                elif isinstance(get_att, str):
                    # Fn::GetAtt can also be "LogicalId.Attribute" string form
                    resource_id = get_att.split(".")[0]
                    if resource_id in conditional_resources and not inside_fn_if:
                        violations.append(("Fn::GetAtt", resource_id))

            # Recurse into all values of the dict
            for key, value in node.items():
                if key not in ("Ref", "Fn::GetAtt"):
                    violations.extend(
                        self._find_unguarded_refs(value, conditional_resources, inside_fn_if)
                    )

        elif isinstance(node, list):
            for item in node:
                violations.extend(
                    self._find_unguarded_refs(item, conditional_resources, inside_fn_if)
                )

        return violations

    def test_unconditional_resources_do_not_reference_conditional_resources_without_fn_if(
        self, template
    ):
        """Unconditional resources must not Ref or Fn::GetAtt conditional resources outside Fn::If."""
        conditional_resources = self._get_conditional_resources(template)
        unconditional_resources = self._get_unconditional_resources(template)

        all_violations = []

        for logical_id in unconditional_resources:
            resource = template["Resources"][logical_id]
            properties = resource.get("Properties", {})
            violations = self._find_unguarded_refs(properties, conditional_resources)
            for ref_type, target_id in violations:
                all_violations.append(
                    f"Resource '{logical_id}' references conditional resource "
                    f"'{target_id}' via {ref_type} without Fn::If guard"
                )

        assert not all_violations, (
            "Found unconditional resources referencing conditional resources "
            f"without Fn::If protection:\n" + "\n".join(f"  - {v}" for v in all_violations)
        )
